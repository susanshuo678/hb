import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

class PosterService:
    @staticmethod
    def generate_poster(user_id: int, username: str, base_url: str):
        # 1. 准备底图 (建议放在 static/img/poster_bg.jpg)
        bg_path = "app/static/img/poster_bg.jpg"
        if not os.path.exists(bg_path):
            # 如果没有底图，创建一个纯白底图
            img = Image.new('RGB', (750, 1334), color='#d00000')
        else:
            img = Image.open(bg_path)

        draw = ImageDraw.Draw(img)
        
        # 2. 生成二维码
        invite_url = f"{base_url}/register?invite={user_id}"
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(invite_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").resize((200, 200))
        
        # 3. 粘贴二维码 (放在底部中间)
        img_w, img_h = img.size
        qr_x = (img_w - 200) // 2
        qr_y = img_h - 300
        img.paste(qr_img, (qr_x, qr_y))
        
        # 4. 绘制文字 (昵称)
        # 尝试加载字体，如果没有则使用默认
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
            
        text = f"我是 {username}"
        # 获取文字宽高 (兼容性写法)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
        except:
            text_w = len(text) * 20 # 估算
            
        draw.text(((img_w - text_w) // 2, qr_y - 60), text, fill="white", font=font)
        draw.text(((img_w - 300) // 2, qr_y + 210), "扫码加入 红白悬赏", fill="white", font=font)

        # 5. 输出
        output = BytesIO()
        img.save(output, format='JPEG', quality=85)
        return output.getvalue()