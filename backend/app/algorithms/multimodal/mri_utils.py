# mri_utils.py
import os
import cv2
import json
import numpy as np
import SimpleITK as sitk

__all__ = [
    "load_dicom",
    "preprocess",
    "save_radii_to_json",
    "find_femoral_heads_from_mask",
]

# ======================== 公共函数 ========================
def load_dicom(image_path):
    """读取 DICOM -> (numpy_array, (spacing_x, spacing_y))；失败返回 (None, None)"""
    try:
        image = sitk.ReadImage(image_path)
        array = sitk.GetArrayFromImage(image)
        pixel_spacing = image.GetSpacing()[:2] if image.GetDimension() >= 2 else None
        if array.ndim == 3 and array.shape[0] == 1:
            array = array[0]
        return array, pixel_spacing
    except Exception as e:
        print(f"❌ 读取DICOM失败: {os.path.basename(image_path)}，错误: {e}")
        return None, None

def preprocess(image_array):
    """轻度预处理：归一化 + CLAHE + 高斯去噪，用于稳定轮廓提取"""
    image_float = image_array.astype(np.float32)
    normalized = cv2.normalize(image_float, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(clahe.apply(normalized))
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    return blurred

# mri_utils.py (修改部分)
def save_radii_to_json(dcm_path, detection_results, pixel_spacing, output_dir):
    """
    仅保存左右中心点坐标到 JSON；不再保存半径、能量。
    JSON 格式：
    {
        "left_femoral_head": {"x": int, "y": int},
        "right_femoral_head": {"x": int, "y": int}
    }
    """
    import os, json
    # 删除原有的output_dir定义，改为使用传入的output_dir
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(dcm_path))[0]
    save_path = os.path.join(output_dir, f"radii_{base_name}.json")

    left_center = {"x": 0, "y": 0}
    right_center = {"x": 0, "y": 0}

    # detection_results: [{'side':'left'|'right', 'center':(x,y), ...}, ...]
    for res in detection_results:
        if res.get('side') == 'left':
            c = res['center']
            left_center = {"x": int(c[0]), "y": int(c[1])}
        elif res.get('side') == 'right':
            c = res['center']
            right_center = {"x": int(c[0]), "y": int(c[1])}

    data = {
        "left_femoral_head": left_center,
        "right_femoral_head": right_center
    }

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"✅ 已保存中心点: {save_path}")






def find_femoral_heads_from_mask(mri_array, config):
    """
    在限定的左右ROI中执行股骨头检测：
    1. 预处理整个图像
    2. 根据配置参数裁剪出左右ROI区域
    3. 在每个ROI内使用凸包策略定位股骨头
    4. 用最小外接圆拟合股骨头轮廓
    返回: (detection_results, roi_contours)；若失败返回 ([], None)
    detection_results: [{'side': 'left'|'right', 'center': (x,y), 'radius': px, 'energy': 1.0}, ...]
    """
    if mri_array is None:
        return [], None
        
    # 1. 预处理整个图像
    processed_img = preprocess(mri_array)
    if processed_img is None:
        return [], None
    
    height, width = processed_img.shape
    
    # 2. 计算限定区域的边界
    top_bound = int(height * config['VERTICAL_CROP'][0])
    bottom_bound = int(height * config['VERTICAL_CROP'][1])
    left_bound = int(width * config['HORIZONTAL_CROP'][0])
    right_bound = int(width * config['HORIZONTAL_CROP'][1])
    
    # 3. 创建左侧ROI和右侧ROI
    left_roi = processed_img[top_bound:bottom_bound, 0:left_bound]
    right_roi = processed_img[top_bound:bottom_bound, right_bound:width]
    
    # 存储结果和轮廓
    results = []
    roi_contours = {"left": None, "right": None}
    
    # 4. 处理左侧ROI
    if left_roi.size > 0:
        left_result, left_contour = process_roi(left_roi, config, "left", top_bound, 0)
        if left_result:
            results.append(left_result)
            roi_contours["left"] = left_contour
    
    # 5. 处理右侧ROI
    if right_roi.size > 0:
        right_result, right_contour = process_roi(right_roi, config, "right", top_bound, right_bound)
        if right_result:
            results.append(right_result)
            roi_contours["right"] = right_contour
    
    return results, roi_contours

def process_roi(roi_image, config, side, y_offset, x_offset):
    """
    处理单个ROI区域，检测股骨头
    """
    # 1. 二值化ROI图像
    _, binary = cv2.threshold(roi_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 2. 形态学操作（腐蚀）以去除小噪点
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    eroded = cv2.erode(binary, kernel, iterations=config['ERODE_ITERATIONS'])
    
    # 3. 查找轮廓
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 如果没有找到轮廓，返回空结果
    if not contours:
        #print(f"❌ {side} ROI内未找到任何轮廓")
        return None, None
    
    # 4. 找到ROI内最大的轮廓
    main_contour = max(contours, key=cv2.contourArea)
    
    # 5. 检查轮廓面积是否满足最小要求
    if cv2.contourArea(main_contour) < config['MIN_AREA']:
        #print(f"❌ {side} ROI内轮廓面积过小: {cv2.contourArea(main_contour)} < {config['MIN_AREA']}")
        return None, None
    
    # 6. 创建凸包
    convex_hull = cv2.convexHull(main_contour)
    
    # 7. 直接从掩码轮廓拟合圆
    if len(convex_hull) < 5:
        #print(f"❌ {side} 侧凸包点数不足，无法拟合圆")
        return None, None
    
    (x, y), radius = cv2.minEnclosingCircle(convex_hull)
    center = (int(x) + x_offset, int(y) + y_offset)  # 调整到原图坐标系
    radius_i = int(radius)
    
    convex_hull_global = convex_hull + np.array([x_offset, y_offset])
    
    return {
        'side': side,
        'center': center,
        'radius': radius_i,
        'energy': 1.0  # 直接拟合，能量定义为1.0占位
    }, convex_hull_global