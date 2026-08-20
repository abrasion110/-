# -*- coding: utf-8 -*-
import os
from PIL import Image
import numpy as np


# =============================================================
# ۱. تفکیک رنگ‌های تصویر (کوانتیزه کردن به N رنگ غالب)
# =============================================================
def detect_layers(input_image_path, n_colors=8):
    img = Image.open(input_image_path).convert('RGB')

    # کوانتیزه کردن به N رنگ غالب (رنگ‌های نزدیک به هم یکی می‌شوند)
    quantized = img.quantize(colors=n_colors, method=Image.MEDIANCUT)
    quantized_rgb = quantized.convert('RGB')
    arr = np.array(quantized_rgb)

    colors, counts = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(-counts)  # از پرتکرار به کم‌تکرار

    layers = []
    for rank, idx in enumerate(order, start=1):
        color = tuple(int(c) for c in colors[idx])
        mask = np.all(arr == colors[idx], axis=-1)
        pct = 100 * counts[idx] / arr.size * 3  # arr.size شامل ۳ کانال است
        layers.append({
            "id": rank,
            "color": color,
            "mask": mask,
            "pct": pct,
        })
    return img.size, layers


def print_layers(layers):
    print("
لایه‌های شناسایی‌شده:")
    for L in layers:
        r, g, b = L["color"]
        print(f"  لایه {L['id']:>2} : RGB({r:3d},{g:3d},{b:3d})  -  {L['pct']:5.2f}% تصویر")
    print()


# =============================================================
# ۲. ذخیره یک ماسک به‌صورت PNG با پس‌زمینه‌ی شفاف
# =============================================================
def save_mask_as_png(mask, fill_color, size, out_path):
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    r, g, b = fill_color
    rgba[..., 0] = r
    rgba[..., 1] = g
    rgba[..., 2] = b
    rgba[..., 3] = np.where(mask, 255, 0)
    Image.fromarray(rgba, mode="RGBA").save(out_path, dpi=(300, 300))


# =============================================================
# ۳. حالت‌های کاری
# =============================================================
def mode_save_all_separate(layers, size, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for L in layers:
        out_path = os.path.join(output_dir, f"layer_{L['id']}.png")
        save_mask_as_png(L["mask"], L["color"], size, out_path)
        print(f"  ذخیره شد: {out_path}")


def mode_merge_layers(layers, size, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    ids_input = input("شماره‌ی لایه‌هایی که می‌خواهید ادغام شوند را با کاما وارد کنید (مثلاً 2,3): ").strip()
    ids = [int(x) for x in ids_input.split(",") if x.strip().isdigit()]

    color_input = input("رنگ نهایی برای این لایه‌ی ادغام‌شده را وارد کنید (R,G,B) مثلاً 0,0,0 برای مشکی: ").strip()
    r, g, b = [int(x) for x in color_input.split(",")]

    merged_mask = np.zeros_like(layers[0]["mask"])
    for L in layers:
        if L["id"] in ids:
            merged_mask |= L["mask"]

    # ذخیره‌ی لایه‌ی ادغام‌شده
    merged_name = "_".join(str(i) for i in ids)
    out_path = os.path.join(output_dir, f"layer_merged_{merged_name}.png")
    save_mask_as_png(merged_mask, (r, g, b), size, out_path)
    print(f"  ذخیره شد: {out_path}")

    # بقیه‌ی لایه‌ها هم جداگانه ذخیره شوند
    for L in layers:
        if L["id"] not in ids:
            out_path = os.path.join(output_dir, f"layer_{L['id']}.png")
            save_mask_as_png(L["mask"], L["color"], size, out_path)
            print(f"  ذخیره شد: {out_path}")


def mode_delete_layers(layers, size, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    ids_input = input("شماره‌ی لایه‌هایی که می‌خواهید حذف شوند را با کاما وارد کنید (مثلاً 4,5): ").strip()
    ids_to_delete = set(int(x) for x in ids_input.split(",") if x.strip().isdigit())

    for L in layers:
        if L["id"] in ids_to_delete:
            print(f"  حذف شد: لایه {L['id']}")
            continue
        out_path = os.path.join(output_dir, f"layer_{L['id']}.png")
        save_mask_as_png(L["mask"], L["color"], size, out_path)
        print(f"  ذخیره شد: {out_path}")


# =============================================================
# ۴. برنامه‌ی اصلی
# =============================================================
if __name__ == "__main__":
    input_file = "image.png"
    output_dir = "layers"

    if not os.path.exists(input_file):
        raise SystemExit(1)

    n_colors_input = input("چند رنگ/لایه در تصویر شناسایی شود؟ (پیش‌فرض 6): ").strip()
    n_colors = int(n_colors_input) if n_colors_input.isdigit() else 6

    print("در حال تفکیک رنگ‌ها...")
    size, layers = detect_layers(input_file, n_colors=n_colors)
    print_layers(layers)

    print("چه کاری می‌خواهید انجام دهید؟")
    print("  1) هر لایه را جداگانه ذخیره کن")
    print("  2) چند لایه را با هم ادغام و به یک رنگ خاص تبدیل کن (بقیه هم جدا ذخیره شوند)")
    print("  3) یک یا چند لایه را حذف کن و باقی‌مانده را جداگانه ذخیره کن")
    choice = input("انتخاب شما (1/2/3): ").strip()

    if choice == "1":
        mode_save_all_separate(layers, size, output_dir)
    elif choice == "2":
        mode_merge_layers(layers, size, output_dir)
    elif choice == "3":
        mode_delete_layers(layers, size, output_dir)
    else:
        print("انتخاب نامعتبر بود. برنامه متوقف شد.")
        raise SystemExit(1)

    print(f"
پایان کار. فایل‌ها در پوشه‌ی '{output_dir}/' ذخیره شدند.")
