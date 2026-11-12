
import jwt
from jwt import PyJWKClient
from ..config import settings

jwks_client = PyJWKClient(settings.JWT_URL)

def verify_token(token):
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
        token,
        signing_key,
        options={"require": ["exp", "iss", "aud", "sub"]},
        audience="terranaut",
        issuer="terranaut",
        algorithms=["RS256"],
        )
    except jwt.ExpiredSignatureError, as e:
        print(e) #tmp
    return payload['sub']