# from datetime import datetime, timedelta
# from jose import jwt, JWTError
# from passlib.context import CryptContext

# SECRET_KEY = "CHANGE_THIS_TO_ENV_LATER"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 1440

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# def hash_password(password: str) -> str:
#     return pwd_context.hash(password)

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return pwd_context.verify(plain_password, hashed_password)

# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# from jose import JWTError, jwt
# from fastapi import HTTPException, status

# def decode_access_token(token: str) -> dict:
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token",
#         )

# REFRESH_TOKEN_EXPIRE_DAYS = 7
# def create_refresh_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
#     to_encode.update({
#         "exp": expire,
#         "type": "refresh"
#     })
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
# def decode_token(token: str):
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except JWTError:
#         return None
