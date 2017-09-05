#!/usr/bin/env python3
'''
module BookmarkServer is a URI shortener that maintains a mapping (dictionary)
between short names and long URIs, checking that each new URI added to the
mapping actually works (i.e. returns a 200 OK).

This server is intended to serve three kinds of requests:

  * A GET request to the / (root) path.  The server returns a form allowing
    the user to submit a new name/URI pairing.  The form also includes a
    listing of all the known pairings.
  * A POST request containing "longuri" and "shortname" fields.  The server
    checks that the URI is valid (by requesting it), and if so, stores the
    mapping from shortname to longuri in its dictionary.  The server then
    redirects back to the root path.
  * A GET request whose path contains a short name.  The server looks up
    that short name in its dictionary and redirects to the corresponding
    long URI.
'''
from socketserver import ThreadingMixIn
from urllib.parse import unquote, parse_qs, urlparse
import http.server
import os
import requests

class ThreadHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    "This is an HTTPServer that supports thread-based concurrency."


MEMORY = {}

FORM = '''<!DOCTYPE html>
<title>Bookmark Server</title>
<form method="POST">
    <label>Long URI:
        <input name="longuri">
    </label>
    <br>
    <label>Short name:
        <input name="shortname">
    </label>
    <br>
    <button type="submit">Save it!</button>
</form>
<p>URIs I know about:
<pre>
{}
</pre>
'''

def check_uri(uri: str) -> bool:
    '''
    Check whether this URI is reachable, i.e. does it return a 200 OK?

    This function returns True if a GET request to uri returns a 200 OK, and
    False if that GET request returns any other response, or doesn't return
    (i.e. times out).
    '''
    final_uri = auto_prefix(uri)
    try:
        req = requests.get(final_uri)
        return req.status_code
    except requests.RequestException:
        return False

def auto_prefix(uri: str) -> str:
    '''
    auto_prefix prepends https:// if it is missing from the input.
    '''
    final_uri = uri
    parsed = urlparse(uri)
    if parsed.scheme == '':
        final_uri = "https://" + uri
        return final_uri
    else:
        return final_uri

class Shortener(http.server.BaseHTTPRequestHandler):
    '''
    Shortener executes matching a short URI to its long counterpart.
    '''
    def do_GET(self) -> None:
        ''' do_GET requests / (the root path) or for /some-name. '''
        # Strip off the / and we have either empty string or a name.
        name = unquote(self.path[1:])

        if name:
            if name in MEMORY:
                # 2. Send a 303 redirect to the long URI in memory[name].
                self.send_response(303)
                self.send_header('Location', MEMORY[name])
                self.end_headers()
            else:
                # We don't know that name! Send a 404 error.
                self.send_response(404)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write("I don't know '{}'.".format(name).encode())
        else:
            # Root path. Send the form.
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # List the known associations in the form.
            known = "\n".join("{} : {}".format(key, MEMORY[key])
                              for key in sorted(MEMORY.keys()))
            self.wfile.write(FORM.format(known).encode())

    def do_POST(self) -> None:
        ''' do_POST decodes the form data. '''
        length = int(self.headers.get('Content-length', 0))
        body = self.rfile.read(length).decode()
        params = parse_qs(body)

        # Check that the user submitted the form fields.
        if "longuri" not in params or "shortname" not in params:
            # 3. Serve a 400 error with a useful message.
            self.send_response(400)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write("You forgot to attach params!".encode())
            return

        longuri = auto_prefix(params["longuri"][0])
        shortname = params["shortname"][0]

        if check_uri(longuri):
            # This URI is good!  Remember it under the specified name.
            MEMORY[shortname] = longuri
            # 4. Serve a redirect to the root page (the form).
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        else:
            # Didn't successfully fetch the long URI.
            # 5. Send a 404 error with a useful message.
            self.send_response(404)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write("Couldn't fetch URI '{}'. Sorry!".format(longuri).encode())

if __name__ == '__main__':
    try:
        PORT = int(os.environ.get('PORT', 8000))
        SERVER_ADDRESS = ('', PORT)
        HTTPD = ThreadHTTPServer(SERVER_ADDRESS, Shortener)
        HTTPD.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down. Bye for now 👋")