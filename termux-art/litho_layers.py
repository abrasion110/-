import os
from PIL import Image
import numpy as np


def generate_litho_layers(input_image_path, output_dir="layers"):
    if not os.path.exists(input_image_path):
        print(f"Error: Input file '{input_image_path}' not found!")
        return

    os.makedirs(output_dir, exist_ok=True)
    print("Processing image and separating layers...")

    img = Image.open(input_image_path).convert('L')
    img_array = np.array(img)

    # -----------------------------------------------------------------
    # بازه‌های خاکستری رو اینجا تعریف کنید. هر بازه = یک لایه جدا.
    # (نام لایه، حد پایین، حد بالا)
    # -----------------------------------------------------------------
    layers = [
        ("black_text_100",   0,   30),   # مشکی خالص - متون و خطوط تیز
        ("halftone_65pct",  30,  230),   # ترام ۶۵٪ - قطعات یدکی/خاکستری میانه
        ("white_bg",        230, 256),   # سفید - پس‌زمینه و کادرها
    ]

    combined_output = np.full(img_array.shape, 255, dtype=np.uint8)

    for name, low, high in layers:
        mask = (img_array >= low) & (img_array < high)

        # ۱) فایل ماسک سیاه/سفید (برای دیدن دقیق ناحیه‌ی لایه)
        mask_img = Image.fromarray(np.where(mask, 0, 255).astype(np.uint8))
        mask_path = os.path.join(output_dir, f"{name}_mask.png")
        mask_img.save(mask_path, dpi=(300, 300))

        # ۲) فایل PNG با پس‌زمینه‌ی شفاف که فقط همون لایه توش دیده میشه
        #    (برای ایمپورت جدا تو فتوشاپ/ایلاستریتور و ویرایش مستقل)
        rgba = np.zeros((*img_array.shape, 4), dtype=np.uint8)
        rgba[..., 0:3] = 0  # مشکی
        rgba[..., 3] = np.where(mask, 255, 0)  # آلفا فقط تو ناحیه‌ی لایه
        layer_img = Image.fromarray(rgba, mode="RGBA")
        layer_path = os.path.join(output_dir, f"{name}_layer.png")
        layer_img.save(layer_path, dpi=(300, 300))

        print(f"  -> {name}: {mask_path} , {layer_path}")

        # مقدار تراکم واقعی هر لایه رو برای TIFF نهایی هم ست کن
        if name == "black_text_100":
            combined_output[mask] = 0
        elif name == "halftone_65pct":
            combined_output[mask] = 90
        elif name == "white_bg":
            combined_output[mask] = 255

    # فایل TIFF نهایی ترکیبی (همون خروجی قبلی، آماده‌ی چاپ افست)
    final_path = os.path.join(output_dir, "rayzan_offset_ready.tif")
    final_img = Image.fromarray(combined_output)
    final_img.save(final_path, format='TIFF', dpi=(300, 300), compression='tiff_lzw')
    print(f"\nSuccess! Combined TIFF saved at: {final_path}")
    print(f"Individual layers saved in: {output_dir}/")


if __name__ == "__main__":
    input_file = "image.png"
    output_directory = "layers"

    generate_litho_layers(input_file, output_directory)
