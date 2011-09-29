$(function() {
    if (!window.console) window.console = {};
    if (!window.console.log) window.console.log = function() {};
    
    var validateForm = function() {
        var ok = true;
        var fields = [$("#teamname"), $("#codefile")];
        for (i in fields) {
            var field = fields[i];
            if (field.val() == "") {
                ok = false;
                field.parents(".field").addClass("error");
            } else {
                field.parents(".field").removeClass("error");
            }
        }
        return ok;
    };

    $("#submit-form").submit(function() {
        if (validateForm()) {
            $("#submit-btn").prop("disabled", true);
            $.post($(this).attr("action"), $(this).serialize(), function() {
                $("#submit-btn").prop("disabled", false);
                $("#submit-form")[0].reset();
            });
        }
        return false;
    });
    
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
        $.get("/submissions", function(data) {
            $("#history-data").html(data);
        }, "html");
    };
    
    setTimeout(function() { updater.poll(); }, 0);
});
