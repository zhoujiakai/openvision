import time
from dataclasses import dataclass
from functools import cached_property
from io import BytesIO
from typing import Optional

import cv2
import numpy as np
from alibabacloud_facebody20191230 import models
from alibabacloud_facebody20191230.client import Client
from alibabacloud_facebody20191230.models import AddFaceAdvanceRequest, CreateFaceDbRequest, AddFaceEntityRequest, \
    SearchFaceAdvanceRequest, DeleteFaceEntityRequest, ListFaceEntitiesRequest
from alibabacloud_tea_openapi.models import Config
from alibabacloud_tea_util.models import RuntimeOptions

from aliyun_face.config import cfg
from aliyun_face.logger import create_logger

# 获取 logger
logger = create_logger("阿里云人脸识别")


def api_call(max_retries=1, delay=1.0):
    """
    API 调用装饰器：统一处理日志、异常捕获和限流重试

    Args:
        max_retries: 最大重试次数（默认1次不重试）
        delay: 初始重试延迟（秒）
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            current_delay = delay
            result = None
            for attempt in range(max_retries):
                try:
                    # 调用原始方法获取 request 和 client_function
                    ali_request, client_function = func(self, *args, **kwargs)
                    # 输出发送的参数
                    cfg.face.LOG and logger.info(f"请求参数：{ali_request.to_map()}")
                    # 发送请求
                    response = client_function(ali_request, self.runtime_option)
                    # 输出请求返回的消息
                    cfg.face.LOG and logger.info(f"返回消息：{response.body}")
                    return response
                except Exception as error:
                    # 获取整体报错信息
                    cfg.face.LOG and logger.warning(f"返回错误：{error}")
                    # 检查是否还能重试
                    if attempt < max_retries - 1:
                        logger.warning(f"  限流，{current_delay}秒后重试 ({attempt + 1}/{max_retries})...")
                        time.sleep(current_delay)
                        current_delay *= 2  # 指数退避
            return result
        return wrapper
    return decorator


@dataclass
class FaceInfo:
    """人脸信息结果"""
    name: str = ""
    face_coors_abs: tuple = ()  # (x1, y1, x2, y2)

class AliyunFaceClient:

    @cached_property
    def client(self):
        """ 获取阿里云客户端（缓存） """
        return Client(Config(
            access_key_id=cfg.face.ACCESS_KEY,
            access_key_secret=cfg.face.SECRET_KEY,
            endpoint=cfg.face.ENDPOINT
        ))

    @cached_property
    def runtime_option(self):
        """ 获取运行时选项（缓存） """
        return RuntimeOptions()

    @staticmethod
    def _preprocess_image(image_path, max_size=2000):
        """ 预处理图片：调整大小、统一格式 """
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"无法读取图片: {image_path}")

        h, w = img.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return BytesIO(buffer.tobytes())

    @api_call()
    def create_database(self, db_name):
        """ 创建人脸数据库 """
        ali_request = CreateFaceDbRequest(name=db_name)
        client_function = self.client.create_face_db_with_options
        return ali_request, client_function

    @api_call()
    def add_entity(self, db_name, person_name):
        """ 创建人脸实例 """
        ali_request = AddFaceEntityRequest(db_name=db_name, entity_id=person_name)
        client_function = self.client.add_face_entity_with_options
        return ali_request, client_function

    @api_call()
    def add_data_local(self, db_name, image_path, name_en, name_cn):
        """ 将本地图片添加到某个人脸实例 """
        ali_request = AddFaceAdvanceRequest()
        ali_request.image_url_object = self._preprocess_image(image_path)
        ali_request.db_name = db_name
        ali_request.entity_id = name_en
        ali_request.extra_data = name_cn
        client_function = self.client.add_face_advance
        return ali_request, client_function

    @api_call()
    def search_face(self, db_name, image_path):
        """ 进行人脸搜索1:N """
        ali_request = SearchFaceAdvanceRequest()
        ali_request.image_url_object = self._preprocess_image(image_path)
        ali_request.db_name = db_name
        ali_request.limit = 1
        client_function = self.client.search_face_advance
        return ali_request, client_function

    def get_face_info(self, db_name: str, image: np.ndarray) -> FaceInfo:
        """ 返回业务需求的人脸信息 """
        face_info = FaceInfo()
        response = self._search_face_advance(db_name, image)
        if not response:
            return face_info
        try:
            cfg.face.LOG and logger.info(f"人员信息：{response.body}")
            result = response.body.to_map()
            name_cn = result['Data']['MatchList'][0]['FaceItems'][0]['ExtraData']
            location = result['Data']['MatchList'][0]['Location']
            face_coors = (location['X'], location['Y'],
                          location['X'] + location['Width'],
                          location['Y'] + location['Height'])
            face_info.name = name_cn
            face_info.face_coors_abs = face_coors
            return face_info
        except Exception as error:
            return face_info

    @api_call()
    def _search_face_advance(self, db_name: str, image: np.ndarray):
        """ get_face_info 的内部辅助方法 """
        ali_request = SearchFaceAdvanceRequest()
        _, buffer = cv2.imencode('.jpg', image)
        ali_request.image_url_object = BytesIO(buffer.tobytes())
        ali_request.db_name = db_name
        ali_request.limit = 1
        client_function = self.client.search_face_advance
        return ali_request, client_function

    @api_call()
    def delete_database(self, db_name):
        """ 删除人脸数据库 """
        ali_request = models.DeleteFaceDbRequest(name=db_name)
        client_function = self.client.delete_face_db_with_options
        return ali_request, client_function

    @api_call(max_retries=3, delay=1.0)
    def delete_entity(self, db_name, entity_id):
        """ 删除人脸数据库中的某个实例（带限流重试） """
        ali_request = DeleteFaceEntityRequest(db_name=db_name, entity_id=entity_id)
        client_function = self.client.delete_face_entity_with_options
        return ali_request, client_function

    @api_call()
    def get_entities(self, db_name=cfg.face.DATABASE_NAME, limit=200, offset=0):
        """ 获取人脸数据库中的所有实例 """
        ali_request = ListFaceEntitiesRequest(db_name=db_name, limit=limit, offset=offset)
        client_function = self.client.list_face_entities_with_options
        return ali_request, client_function


# 全局单例客户端
_client_instance: Optional[AliyunFaceClient] = None


def get_face_client() -> AliyunFaceClient:
    """
    获取阿里云人脸识别客户端单例

    Returns:
        AliyunFaceClient 实例
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = AliyunFaceClient()
    return _client_instance


def main():
    from pathlib import Path

    client = get_face_client()
    db_name = cfg.face.DATABASE_NAME
    assets_dir = Path(__file__).parent.parent / "assets" / "faces"

    # 检查并重建数据库
    response = client.get_entities(db_name, limit=1)
    if response:
        logger.info(f"数据库 {db_name} 已存在，正在删除...")
        # 先获取并删除所有实体（带重试机制）
        entities = client.get_entities(db_name, limit=200)
        if entities:
            result = entities.body.to_map()
            deleted_count = 0
            failed_entities = []
            for entity in result.get('Data', {}).get('Entities', []):
                entity_id = entity.get('EntityId')
                logger.info(f"  删除实体: {entity_id}")
                result = client.delete_entity(db_name, entity_id)
                if result:
                    deleted_count += 1
                else:
                    failed_entities.append(entity_id)
                    logger.warning(f"    删除失败: {entity_id}")

            if failed_entities:
                logger.warning(f"  {len(failed_entities)} 个实体删除失败: {failed_entities}")
                logger.info("  继续尝试删除数据库...")
            else:
                logger.info(f"  成功删除 {deleted_count} 个实体")

        # 再删除数据库
        client.delete_database(db_name)

    logger.info(f"正在创建数据库 {db_name}...")
    create_result = client.create_database(db_name)
    if not create_result:
        logger.info(f"数据库 {db_name} 已存在，跳过创建")

    # 中文名 -> entity_id 映射
    name_map = {
        "范冰冰": "fanbingbing",
        "胡歌": "hu_ge",
        "林志玲": "linzhiling",
        "唐嫣": "tangyan",
    }

    # 1. 添加实体和人脸
    for name_cn, name_en in name_map.items():
        folder = assets_dir / name_cn
        if not folder.exists():
            continue
        # 添加实体（忽略已存在错误）
        client.add_entity(db_name, name_en)
        # 添加训练图片
        for img in sorted(folder.glob("*.jpg")):
            logger.info(f"添加 {name_cn}: {img.name}")
            result = client.add_data_local(db_name, img, name_en, name_cn)
            if not result:
                logger.warning(f"    添加失败（可能已达到5张上限）: {img.name}")

    # 2. 测试搜索
    for name_cn, name_en in name_map.items():
        test_img = assets_dir / f"{name_cn}.05.jpg"
        if test_img.exists():
            logger.info(f"测试搜索: {test_img.name}")
            response = client.search_face(db_name, test_img)
            if response:
                result = response.body.to_map()
                matched = result['Data']['MatchList'][0]['FaceItems'][0]['ExtraData']
                logger.info(f"  识别结果: {matched}")


if __name__ == '__main__':
    main()
