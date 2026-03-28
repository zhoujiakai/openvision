# rk3588部署yolo11m

## 将yolo11从pt转换成onnx

### 引用

**参考这个教程和仓库**

- 链接：https://github.com/yuking926/RKNN-YOLO11
- 类型：github

### 位置

openvision/yolo11_convert_pt2onnx/

### 命令

下载本仓库，进入仓库文件夹，然后执行以下命令

```shell
# 创建虚拟环境
conda create -n pt2onnx2 python=3.10
conda activate pt2onnx2

# 安装依赖
cd yolo11_convert_pt2onnx
pip install -e .
pip install onnxscript
pip install torch==2.3.1 torchvision==0.18.1

# 下载pt模型
python download.py

# 转换成onnx
export PYTHONPATH=./
python ./ultralytics/engine/exporter.py
```

![转换完成](../../../../同步空间/Dao/assets/截屏2026-03-28 下午5.57.13.png)

​											图-pt转换成onnx完成