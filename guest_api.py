"""HTTPS transport for the public academic guest booking API.

The legacy anon JWT is a public gateway credential, not a database password.
Privileged service credentials remain within the Supabase Edge Function.
"""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from postgres_adapter import DatabaseUnavailable

URL = 'https://gaeqzqgpxbuwlartufts.supabase.co/functions/v1/ewu-guest-portal'
ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdhZXF6cWdweGJ1d2xhcnR1ZnRzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTU1MDQ5OTQsImV4cCI6MjExMTA4MDk5NH0.sCL6WAR1aAGH39_XOgGrcYU9GdJcvi1JXyjiVqB6e2g'


def guest_rpc(action, data=None):
    payload = json.dumps({'action': action, 'data': data or {}}).encode('utf-8')
    request = Request(URL, data=payload, method='POST', headers={
        'apikey': ANON_KEY, 'Authorization': 'Bearer ' + ANON_KEY,
        'Content-Type': 'application/json',
    })
    try:
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
            if not isinstance(result, dict):
                raise ValueError('Invalid response')
            return result
    except HTTPError as exc:
        if exc.code == 400:
            try:
                result = json.load(exc)
                if isinstance(result, dict) and isinstance(result.get('error'), str):
                    return result
            except (ValueError, OSError):
                pass
        raise DatabaseUnavailable('guest_api_unavailable') from None
    except (URLError, OSError, ValueError):
        raise DatabaseUnavailable('guest_api_unavailable') from None
