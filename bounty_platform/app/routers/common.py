from fastapi import APIRouter, Response, Request
from captcha.image import ImageCaptcha
import random, string

router = APIRouter(tags=["Common"])

@router.get("/captcha")
async def get_captcha(request: Request):
    image = ImageCaptcha(width=120, height=50) 
    code = "".join(random.choices(string.digits, k=4))
    
    # 存入 Session，5分钟有效期由 Session 中间件管理
    request.session["captcha"] = code
    
    return Response(content=image.generate(code).getvalue(), media_type="image/png")