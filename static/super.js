$(function() {
    if (!window.console) window.console = {};
    if (!window.console.log) window.console.log = function() {};
    
    var should_blink = false;
    
    var alternateTitle = "||||| " + document.title + " |||||";
    var blinker;
    blinker = function() {
        if (should_blink) {
            var tmp = alternateTitle;
            alternateTitle = document.title;
            document.title = tmp;
        }
        setTimeout(blinker, 1000);
    };
    setTimeout(blinker, 0);
    
    var updater = {
        ERROR_SLEEP_TIME: 10000,
        cursor: -1,
    };
    
    updater.poll = function() {
        $.get("/update", {cursor: this.cursor}, function(data) {
            updater.cursor = data.cursor;
            updater.refresh();
            setTimeout(function() { updater.poll(); }, 0);
        }, "json").error(function() {
            console.log("erro");
            updater.cursor = -1;
            setTimeout(function() { updater.poll(); }, updater.ERROR_SLEEP_TIME); 
        });
    };
    
    updater.refresh = function() {
        $.get("/super/submissions", function(data) {
            should_blink = /<td>\s*new\s*<.td>/.test(data);
            console.log(should_blink);
            $("#history-data").html(data);
        }, "html");
    };
    
    setTimeout(function() { updater.poll(); }, 0);
    
    $("a.ajax").live("click", function() {
        $.get($(this).attr("href"));
        return false;
    });
});
