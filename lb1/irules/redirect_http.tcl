when HTTP_REQUEST {
    if { [HTTP::host] ne "" } {
        HTTP::redirect "https://[HTTP::host][HTTP::uri]"
    }
}
