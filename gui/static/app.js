var padx = 10;
var pady = 5;
var padtop = 15;

var prepareTimeline = function(canvas) {
    var ctx = canvas.getContext("2d");

    var width = canvas.width;
    var height = canvas.height;

    var w = width - 2*padx;
    var h = height - (2*pady + padtop)

    var font = 10;

    ctx.font = font + "px Arial";
    ctx.textAlign = 'center';

    ctx.beginPath();
    ctx.fillStyle = '#c1d9ff';
    ctx.fillRect(padx, pady+padtop, w*(6.5/24), h);

    ctx.beginPath();
    ctx.fillStyle = '#c1d9ff';
    ctx.fillRect(padx + w*(18.5/24), pady+padtop, w*(24-18.5)/24, h);

    ctx.beginPath();
    ctx.fillStyle = '#ffe5bc';
    ctx.fillRect(padx + w*(6.5/24), pady+padtop, w*(18.5-6.5)/24, h);

    for (var i = 0; i <= 24; i++) {
        var xpos = padx + (w * (i/24));
        if (i % 6 == 0)
            ctx.fillStyle = '#f00';
        else
            ctx.fillStyle = '#000';
            
        if (i == 24) {
            ctx.fillStyle = '#bbb';
            ctx.fillText('hr', xpos, 13);
        } else {
            ctx.fillText(i, xpos, 13);
        }

        if (i > 0) {
            ctx.beginPath()
            ctx.lineWidth = 0.1;
            if (i > 6 && i <= 18)
                ctx.strokeStyle = '#f60';
            else
                ctx.strokeStyle = '#00f';

            ctx.moveTo(xpos, pady + padtop);
            ctx.lineTo(xpos, pady + padtop + h);
            ctx.stroke();
        }
    }

    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeWidth = 2;
    ctx.strokeStyle = '#000';
    ctx.strokeRect(padx, pady+padtop, w, h);
}

var drawTimeline = function(canvas, data) {
    var DAY = 86400;
    var ctx = canvas.getContext("2d");

    var width = canvas.width;
    var height = canvas.height;

    var w = width - 2*padx;
    var h = height - (2*pady + padtop)

    var time_now = parseFloat($(canvas).attr('data-current-time'));
    if (time_now > 0 && time_now < 1) {
        ctx.beginPath();
        ctx.fillStyle = '#000';
        ctx.fillRect(time_now * w + padx, pady + padtop, (1-time_now) * w, h);
        // if (time_now < 0.9) {
        //     ctx.beginPath();
        //     ctx.font = "10px Arial";
        //     ctx.fillStyle = '#fff';
        //     ctx.textAlign = 'left';
        //     ctx.fillText('Now', time_now * w + padx + 5, padtop + h - 2);
        // }
    }

    $.each(data, function(_, v) {
        var posx = (v[0]/DAY) * w + padx
        ctx.beginPath();
        ctx.lineWidth = 2;
        if (v[1] == 2)
            ctx.strokeStyle = '#0f0';
        else if (v[1] == 0)
            ctx.strokeStyle = '#090';
        else 
            ctx.strokeStyle = '#aaa';

        ctx.moveTo(posx, pady + padtop);
        ctx.lineTo(posx, pady + padtop + h);
        ctx.stroke();
    });

    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeWidth = 2;
    ctx.strokeStyle = '#000';
    ctx.strokeRect(padx, pady+padtop, w, h);
}

var unquotejson = function(inp) {
    return JSON.parse(inp.replace(/\_/g, 'null').replace(/\\"/g, '"'))
}

var initializeTimeline = function(canvas) {
    prepareTimeline(canvas);
    drawTimeline(canvas, unquotejson($(canvas).attr('data-plot')));
}

$(document).ready(function() {
    $('canvas.timeline').each(function(_, canvas) {
        initializeTimeline(canvas);
    });

    $.ajaxSetup({
        beforeSend: function (jqXHR, settings) {
            if (settings.dataType === 'binary') {
                settings.xhr().responseType = 'arraybuffer';
            }
        }
    })

    $('button.timeline-button').click(function(e) {
        e.preventDefault();
        $(this).addClass('loading disabled');

        var uid = $(this).attr('data-uid');
        var btn = this;

        $.ajax({
            url: '/api/user/' + uid,
            method: 'POST',
            data: {
                'type': 'timeline',
                'seq': parseInt($(btn).attr('data-loaded')) + 1,
            },
            beforeSend: function() {
                $(btn).parent().find('.error-msg').addClass('hidden');
            },
            complete: function(r) {
                $(btn).removeClass('loading disabled');

                if (r.status != 200) {
                    $(btn).parent().find('.error-msg')
                        .text('Connection Failed: ' + r.status + ' (' + r.statusText + ')')
                        .removeClass('hidden');
                    return;
                }

                var pl = JSON.parse(r.responseText);

                if (pl.code == 0) {
                    var html = '<div class="timeline">\
                        <h4 class="timeline-header">' + pl.header + '</h4>\
                        <canvas class="timeline" id="timeline-' + pl.seq + 
                        '" width="600" height="45" data-current-time="1" data-plot="' + pl.payload + '"></canvas>\
                    </div>';
                    $('.timeline-group').append(html);
                    initializeTimeline($('#timeline-'+pl.seq)[0]);
                    $(btn).attr('data-loaded', pl.seq);
                } else {
                    $(btn).parent().find('.error-msg')
                        .text('Error: ' + pl.msg + ' (' + pl.code + ')')
                        .removeClass('hidden');
                    return;
                }
            }
        });
    });
});
