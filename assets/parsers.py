from io import BytesIO

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.parsers import JSONParser


class PayloadTooLarge(APIException):
    status_code = 413
    default_detail = "Request body is too large"
    default_code = "request_too_large"


class BoundedJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        limit = settings.MAX_REQUEST_BODY_SIZE
        content_length = (parser_context or {}).get("content_length")
        if content_length is not None and content_length > limit:
            raise PayloadTooLarge()
        body = stream.read(limit + 1)
        if len(body) > limit:
            raise PayloadTooLarge()
        return super().parse(BytesIO(body), media_type, parser_context)