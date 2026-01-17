from fastapi import APIRouter, Response, Depends, Request
from captcha.image import ImageCaptcha
import random, string, io
from ..core import config

router = APIRouter(tags=["Common"])

@router.get("/captcha")
def get_captcha(request: Request):
    image = ImageCaptcha(width=120, height=50) 
    code = "".join(random.choices(string.digits, k=4))
    
    # V3 优化：验证码存 Redis，5分钟过期
    # request.app.state.redis.setex(f"captcha:{session_id}", 300, code)
    # 简单起见暂时存 Session
    request.session["captcha"] = code
    
    return Response(content=image.generate(code).getvalue(), media_type="image/png")