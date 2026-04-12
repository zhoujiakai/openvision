# YOLO11转换部署到瑞芯微

**位置：**`cd openvision/yolo11_deploy`

**介绍：**

- 转换：将YOLO11从pt格式转换成rknn格式，同时进行int8量化
- 推理：使用python在瑞芯微的板子进行YOLO11的推理。

**详见：**[README_deploy](./deploy/README_deploy.md)



# 阿里云人脸识别客户端

**位置：**`cd openvision/aliyun_face`

**介绍：**

- 使用python调用阿里云的人脸识别接口，操作人脸数据库并获取人脸信息。

- 使用装饰器方法，支持错误重连并简化代码。

**详见：**[README_aliyun_face](./aliyun_face/README_aliyun_face.md)


# 力扣题目

**位置：**`cd openvision/leetcode`

**介绍：**

- 力扣热题100和剑指offer50题。

- 包含简单思路和通关代码。

**详见：**[README_leetcode](./leetcode/README_leetcode.md)

# RTSP多视频流接流

**位置：**

```shell
cd openvision/multi_rtsp
```

**介绍：**

- 异步读取视频帧

- 使用Python、OpenCV实现读取多个rtsp视频流
- 内存缓存视频流序列

**详见：**

[README_multi_rtsp](./multi_rtsp/README_multi_rtsp.md)
