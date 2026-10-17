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


class SecurityHeadersMiddleware:
    """
    Middleware to inject modern, robust Security Headers including
    Content-Security-Policy with 'unsafe-eval' and 'unsafe-inline'
    to allow Alpine.js, HTMX, and Phosphor icons while protecting the application.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com blob:",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://unpkg.com",
            "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://unpkg.com",
            "img-src 'self' data: blob: https: http:",
            "media-src 'self' data: blob: https: http:",
            "connect-src 'self' ws: wss: https: http:",
            "worker-src 'self' blob:",
            "object-src 'none'",
            "base-uri 'self'",
        ]
        response['Content-Security-Policy'] = "; ".join(csp_directives)
        return response
