import os
import cairosvg

def convert_svg_to_png(svg_path, png_path):
    """
    将SVG文件转换为PNG文件
    
    Args:
        svg_path: SVG文件路径
        png_path: PNG文件输出路径
    """
    try:
        cairosvg.svg2png(url=svg_path, write_to=png_path)
        print(f"转换成功: {svg_path} -> {png_path}")
        return True
    except Exception as e:
        print(f"转换失败: {str(e)}")
        return False

if __name__ == '__main__':
    # 确保assets目录存在
    assets_dir = 'assets'
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
    
    # 转换logo.svg为logo.png
    svg_path = os.path.join(assets_dir, 'logo.svg')
    png_path = os.path.join(assets_dir, 'logo.png')
    
    if os.path.exists(svg_path):
        convert_svg_to_png(svg_path, png_path)
    else:
        print(f"错误: 找不到SVG文件 {svg_path}")