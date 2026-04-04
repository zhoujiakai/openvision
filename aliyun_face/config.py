from pathlib import Path

import yaml


class Config:
    BASE_DIR: Path = Path(__file__).resolve().parent
    TEAM: str = "openvision"

    def __init__(self) -> None:
        # 从 config.yaml 加载配置
        self.load_config()

    def load_config(self) -> None:
        config_file_path = self.BASE_DIR / f"config.yaml"
        if not config_file_path.exists():
            return
        with open(config_file_path, encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        for k, v in raw.items():
            if not isinstance(v, dict):
                continue
            section_cls = getattr(self.__class__, k, None)
            if section_cls is None or not isinstance(section_cls, type):
                continue
            for k2, v2 in v.items():
                setattr(section_cls, k2, v2)

    class face:
        """ 人脸识别配置 """
        ACCESS_KEY: str = None  # 阿里云人脸服务密钥
        SECRET_KEY: str = None  # 阿里云人脸服务密钥
        DATABASE_NAME: str = 'face_20260403'  # 数据库名称
        ENDPOINT: str = 'facebody.cn-shanghai.aliyuncs.com'  # 访问的域名
        LOG: int = 1  # 输出接口调用信息，1表示输出，0表示不输出


cfg = Config()

if __name__ == "__main__":
    print(cfg.face.ENDPOINT)
