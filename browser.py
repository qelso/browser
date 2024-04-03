import socket
import ssl

ENTITIES = {
    "&lt;":"<",
    "&gt;":">"
}

SOCKET_CACHE = {

}
class URL():
    def __init__(self,url:str) -> None:
        # https://example.org/resource.html
        # data:text/html,ciaociao
        # view-source:http://oi.it
        if not url:
            url = "file:///home/qelso/dev/browser/home.html"
        
        self.scheme, url = url.split(":", 1) 
        assert self.scheme in ("http", "https","file", "data","view-source") 

        if self.scheme == "view-source":
            self.scheme, url = url.split(":", 1)
            self.viewsource = True
        else:
            self.viewsource = False

        if self.scheme != "data":
            url = url[2:]
            if "/" not in url:
                url = url + "/"
            self.host, url = url.split("/",1)
            self.path = "/" + url    

            if self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443
            
            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)
        else:
            self.host, self.path = url.split(",", 1)
        
        #self.socket = None

    def _add_headers(self, request):
        request += f"Host: {self.host}\r\n"
        #request += f"Connection: close\r\n"
        request += f"User-Agent: Gigachad-browser\r\n"

        request += "\r\n"
        return request
 
    def request(self, redirects=0):
        if self.scheme not in ("file","data"):

            socket_key = f"{self.host}:{self.port}"
            if socket_key in SOCKET_CACHE:
                s = SOCKET_CACHE[socket_key]
            else:
                s = socket.socket(
                    family=socket.AF_INET,
                    type=socket.SOCK_STREAM,
                    proto=socket.IPPROTO_TCP
                )

                s.connect((self.host, self.port))

            if self.scheme == "https":
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=self.host)

            request = f"GET {self.path} HTTP/1.0\r\n"
            request = self._add_headers(request)
            s.send(request.encode("utf8"))
            
            response = s.makefile("r", encoding="utf8", newline="\r\n")
            statusline = response.readline()
            version, status, explanation = statusline.split(" ", 2)

            response_headers = {}
            while True:
                line = response.readline()
                if line == "\r\n": break
                header, value = line.split(":",1)
                response_headers[header.casefold()] = value.strip()
            
            assert "transfer-encoding" not in response_headers
            assert "content-encoding" not in response_headers

            size = -1
            if "content-length" in response_headers:
                size = int(response_headers["content-length"])
            
            if "location" in response_headers and int(status) >= 300 and redirects < 3:
                if response_headers["location"].startswith("/"):
                    new_url = f"{self.scheme}://{self.host}{response_headers['location']}"
                else:
                    new_url = response_headers["location"]
                content = URL(new_url).request(redirects=redirects+1)
            else:
                content = response.read(size)
            response.close()

        elif self.scheme == "file":
            content = open(self.path).read()
        elif self.scheme == "data":
            if self.host == "text/html":     
                content = self.path

        if self.viewsource:
            for e in ENTITIES:
                content = content.replace(ENTITIES[e],e)
        return content
    
def show(body:str):
    in_tag = False
    
    toshow = ""
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            toshow += c
    
    for e in ENTITIES:
        toshow = toshow.replace(e,ENTITIES[e])
    print (toshow)

def load(url:URL):
    body = url.request()
    show(body)

if __name__ == "__main__":
    import sys
    load(URL(sys.argv[1]))
