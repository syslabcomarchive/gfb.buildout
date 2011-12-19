#-e This is a basic VCL configuration file for varnish.  See the vcl(7)
#man page for details on VCL syntax and semantics.
#
#Default backend definition.  Set this to point to your content
#server.
#
backend default {
.host = "127.0.0.1";
.port = "8002";
.first_byte_timeout = 300s;
.connect_timeout = 5s;
}
acl purge {
    "localhost";
}

#Below is a commented-out copy of the default VCL logic.  If you
#redefine any of these subroutines, the built-in logic will be
#appended to your code.
#
#sub vcl_recv {

#    set req.grace = 24h;
#    unset req.http.If-Modified-Since;

#    if (req.request != "GET" &&
#      req.request != "HEAD" &&
#      req.request != "PUT" &&
#      req.request != "POST" &&
#      req.request != "TRACE" &&
#      req.request != "OPTIONS" &&
#      req.request != "DELETE") {
#        /* Non-RFC2616 or CONNECT which is weird. */
#        return (pipe);
#    }
#    if (req.url ~ "@@register" || req.url ~ "@@captcha" || req.url ~ "sign-up$" req.url ~ "sendto_form$") {
#        return (pipe);
#    }
#    set req.http.Cookie = regsuball(req.http.Cookie, "(^|;\s*)(__ut[a-z]+|I18N_LANGUAGE)=[^;]*", "");
#    // Remove a ";" prefix, if present.
#    set req.http.Cookie = regsub(req.http.Cookie, "^;\s*", "");

#    return (lookup);

#}
sub vcl_recv {
    set req.grace = 24h;
    unset req.http.If-Modified-Since;

    # allow PURGE from localhost
    if (req.request == "PURGE") {
	    if (!client.ip ~ purge) {
		    error 405 "Not allowed.";
	    }
	    return (lookup);
    }

    if (req.request != "GET" &&
      req.request != "HEAD" &&
      req.request != "PUT" &&
      req.request != "POST" &&
      req.request != "TRACE" &&
      req.request != "OPTIONS" &&
      req.request != "DELETE") {
        /* Non-RFC2616 or CONNECT which is weird. */
        return (pipe);
    }
    if (req.http.Cookie ~ "I18N_LANGUAGE") {
        set req.http.X-Varnish-Language = regsub(req.http.Cookie, "/I18N_LANGUAGE=(.*)/", "\1");
    }


    if (req.url ~ "@@register") { 
        return (pipe);
    }
    if (req.url ~ "@@captcha") {
        return (pipe);
    }
    if (req.request != "GET" && req.request != "HEAD") {
        /* We only deal with GET and HEAD by default */
        return (pass);
    }
    if (req.http.Authorization || req.http.Cookie) {
        /* Not cacheable by default */
        return (pass);
    }
    return (lookup);
}


#sub vcl_pipe {
#    # Note that only the first request to the backend will have
#    # X-Forwarded-For set.  If you use X-Forwarded-For and want to
#    # have it set for all requests, make sure to have:
#    set req.http.connection = "close";
#    # here.  It is not set by default as it might break some broken web
#    # applications, like IIS with NTLM authentication.
#    return (pipe);
#}
#
#sub vcl_pass {
#    return (pass);
#}
#
sub vcl_hash {
    set req.hash += req.http.X-Varnish-Language;
    set req.hash += req.url;
    if (req.http.host) {
        set req.hash += req.http.host;
    } else {
        set req.hash += server.ip;
    }
    return (hash);
}
sub vcl_hit {
        if (req.request == "PURGE") {
                # Note that setting ttl to 0 is magical.
                # the object is zapped from cache.
                set obj.ttl = 0s;
                error 200 "Purged.";
        }
}

sub vcl_miss {
        if (req.request == "PURGE") {

                error 404 "Not in cache.";
        }
}

#sub vcl_fetch {
#    if (!obj.cacheable) {
#        return (pass);
#    }
#    if (obj.http.Set-Cookie) {
#        return (pass);
#    }
#    set obj.prefetch =  -30s;
#    return (deliver);
#}
#
sub vcl_fetch {
    if (obj.http.Set-Cookie) {
        return (pass);
    }
    if (req.url ~ "/login_form$" || req.http.Cookie ~ "__ac") {
        return (pass);
    }
    set obj.grace = 25h;
    #unset obj.http.Set-Cookie;
    unset obj.http.Pragma;
    unset obj.http.Cache-Control;
    # images should live one day
    if (req.url ~ "\/get_page_image") {
        set obj.ttl = 84600s;
        set obj.http.cache-control = "max-age=84600";
        set obj.http.max-age = "84600";
        set obj.http.expires = "84600";
    }
    if (req.url ~ "\/(image|image_thumb|image_mini)$") {
        set obj.ttl = 1209600s;
        set obj.http.cache-control = "max-age=1209600";
        set obj.http.max-age = "1209600";
        set obj.http.expires = "1209600";
    }
    if (req.url ~ "\.(png|gif|jpg|swf|otf|ttf)$") {
        set obj.ttl = 1209600s;
        set obj.http.cache-control = "max-age=1209600";
        set obj.http.max-age = "1209600";
        set obj.http.expires = "1209600";
    }
    # resource files should live 14 days to make google happy
    if (req.url ~ "\.(css|js|kss)$") {
        set obj.ttl = 1209600s;
        set obj.http.cache-control = "max-age=1209600";
        set obj.http.max-age = "1209600";
        set obj.http.expires = "1209600";
    }
    if (req.url ~ "search_rss") {
        set obj.ttl = 84600s;
        set obj.http.cache-control = "max-age=84600";
        set obj.http.max-age = "84600";
        set obj.http.expires = "84600";
    }

    return (deliver);
}


#
#sub vcl_deliver {
#    return (deliver);
#}
#
#sub vcl_discard {
#    /* XXX: Do not redefine vcl_discard{}, it is not yet supported */
#    return (discard);
#}
#
#sub vcl_prefetch {
#    /* XXX: Do not redefine vcl_prefetch{}, it is not yet supported */
#    return (fetch);
#}
#
#sub vcl_timeout {
#    /* XXX: Do not redefine vcl_timeout{}, it is not yet supported */
#    return (discard);
#}
#
#sub vcl_error {
#    set obj.http.Content-Type = "text/html; charset=utf-8";
#    synthetic {"
#<?xml version="1.0" encoding="utf-8"?>
#<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
# "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
#<html>
#  <head>
#    <title>"} obj.status " " obj.response {"</title>
#  </head>
#  <body>
#    <h1>Error "} obj.status " " obj.response {"</h1>
#    <p>"} obj.response {"</p>
#    <h3>Guru Meditation:</h3>
#    <p>XID: "} req.xid {"</p>
#    <address>
#       <a href="http://www.varnish-cache.org/">Varnish</a>
#    </address>
#  </body>
#</html>
#"};
#    return (deliver);
#}
