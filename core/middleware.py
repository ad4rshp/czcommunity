from django.core.cache import cache
from django.http import HttpResponse
import time

class RateLimitMiddleware:
    """
    Middleware to rate limit authentication requests (login, register).
    Allows 10 requests per 5 minutes per IP.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ['/login/', '/register/'] and request.method == 'POST':
            ip = self.get_client_ip(request)
            cache_key = f"ratelimit_{ip}_{request.path}"
            
            # Get current attempts
            attempts = cache.get(cache_key, 0)
            
            if attempts >= 10:
                return HttpResponse("You have exceeded the maximum number of attempts. Please try again later.", status=429)
                
            # Increment attempts
            cache.set(cache_key, attempts + 1, timeout=300) # 5 minutes

        response = self.get_response(request)
        
        # If login was successful, clear the rate limit
        if request.path == '/login/' and request.method == 'POST' and response.status_code == 302:
            ip = self.get_client_ip(request)
            cache.delete(f"ratelimit_{ip}_{request.path}")
            
        return response
        
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
