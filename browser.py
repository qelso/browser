import socket
import ssl
import datetime
import gzip
import tkinter

ENTITIES = {
    "&lt;":"<",
    "&gt;":">"
}

# CACHES
# TODO: Add better caching strategies
SOCKET_CACHE = {}
CONTENT_CACHE = {}

HEIGHT = 600
EFFECTIVE_HEIGHT = 600
WIDTH = 800
SCROLL_STEP = 100
HSTEP, VSTEP = 13,18
SCROLL_MULTIPLIER = 0

def layout(text):
    display_list = list() 
    cursor_x,cursor_y = HSTEP, VSTEP

    global SCROLL_MULTIPLIER
    global EFFECTIVE_HEIGHT
    
    for c in text:
        display_list.append((cursor_x,cursor_y, c))
        cursor_x += HSTEP   
        
        if c == "\n":
            cursor_x = HSTEP
            cursor_y += VSTEP  

        if cursor_x >= WIDTH - HSTEP:
            cursor_x = HSTEP
            cursor_y += VSTEP         

    SCROLL_MULTIPLIER = HEIGHT/cursor_y
    if SCROLL_MULTIPLIER < 1:
        SCROLL_MULTIPLIER = 1 - SCROLL_MULTIPLIER 
    EFFECTIVE_HEIGHT = cursor_y
    return display_list

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
        request += f"Accept-Encoding: gzip\r\n"

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

            send_request = True
            if request in CONTENT_CACHE:
                content,start_date,max_age = CONTENT_CACHE[request] 
                if (start_date + datetime.timedelta(seconds=max_age)) > (datetime.datetime.now()):
                    send_request = False
                    print("Using cached content")
            
            if send_request:
                s.send(request.encode("utf8"))
            
                response = s.makefile("rb", encoding="utf8", newline="\r\n")
                statusline = response.readline().decode()
                version, status, explanation = statusline.split(" ", 2)
                status = int(status)

                response_headers = {}
                while True:
                    line = response.readline().decode()
                    if line == "\r\n": break
                    header, value = line.split(":",1)
                    response_headers[header.casefold()] = value.strip()
            
                #assert "transfer-encoding" not in response_headers
                #assert "content-encoding" not in response_headers

                size = -1
                if "content-length" in response_headers:
                    size = int(response_headers["content-length"])
            
                if "location" in response_headers and status >= 300 and redirects < 3:
                    if response_headers["location"].startswith("/"):
                        new_url = f"{self.scheme}://{self.host}{response_headers['location']}"
                    else:
                        new_url = response_headers["location"]
                    content = URL(new_url).request(redirects=redirects+1)
                else:
                    content = response.read(size)

                if status == 200:  
                    if "cache-control" in response_headers:
                        options = response_headers["cache-control"].split(",")
                        for opt in options:
                            if "max-age" in opt:
                                max_age = int(opt.split("=", 1)[1])
                                start_date = datetime.datetime.strptime(response_headers["date"],"%a, %d %b %Y %H:%M:%S GMT")
                                CONTENT_CACHE[request] = (content,start_date,max_age)
                            # add handling of must-revalidate directive
                
                if "content-encoding" in response_headers:
                    if "gzip" in response_headers["content-encoding"]:
                        content = gzip.decompress(content).decode()
                else:
                    content = content.decode()
                #TODO: Add transfer-encoding

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
    

class Browser():
    
    def __init__(self) -> None:
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack(expand=True,fill='both')
        self.scroll = 0
        self.window.bind("<Down>",self._scrolldown)
        self.window.bind("<Up>",self._scrollup)
        self.window.bind("<Button-4>",self._scrollup)
        self.window.bind("<Button-5>",self._scrolldown)
        self.canvas.bind("<Configure>",self._resize)
        #self.window.bind("<MouseWheel>",self._scrollwheel)
    
    def _resize(self,ev):
        global HEIGHT,WIDTH
        HEIGHT = ev.height
        WIDTH = ev.width
        self.display_list = layout(self.text)
        self.draw()
    
    def _scrollwheel(self,ev):
        pass
    
    def _scrolldown(self,ev):
        self.scroll += SCROLL_STEP
        self.draw()
     
    def _scrollup(self,ev):
        self.scroll -= SCROLL_STEP
        self.draw()  

    def load(self,url:URL):   
        self.text = self.lex(url.request())
        self.display_list = layout(self.text)
        self.draw()
     
    def draw(self):
        self.canvas.delete("all")

        scroll_y = self.scroll/EFFECTIVE_HEIGHT
        scroll_y = HEIGHT * scroll_y
        self.canvas.create_rectangle(WIDTH-10,scroll_y,WIDTH,5+scroll_y+HEIGHT-(HEIGHT*SCROLL_MULTIPLIER),fill="blue")
        for x,y,c in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue 
            self.canvas.create_text(x,y - self.scroll,text=c)

    def lex(self,body:str): 
        in_tag = False
        text = ""
        for c in body:
            if c == "<":
                in_tag = True
            elif c == ">":
                in_tag = False
            elif not in_tag:
                text += str(c)
        
        for e in ENTITIES:
            text = text.replace(e,ENTITIES[e])

        return text   

if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    #Browser().load(URL("https://developer.mozilla.org/en-US/docs/Learn/JavaScript/First_steps/Math"))
    #Browser().load(URL("https://example.org"))   
    tkinter.mainloop()




