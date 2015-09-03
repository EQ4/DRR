<meta name="description" content="Sending you audio for later enjoyment" />
<meta property="og:site_name" content="Indycast" />
<link rel="stylesheet" href="/assets/css/main.css" />
<link href='http://fonts.googleapis.com/css?family=Inconsolata' rel='stylesheet' type='text/css'>
<link href='http://fonts.googleapis.com/css?family=Lora' rel='stylesheet' type='text/css'>
<style>
h1 { background: white } 
a { cursor: pointer }
#duration { width: 100%; text-align: center }
#duration li { width: 32% }
#podcast-done { display: block }
#podcast-url { line-height: 0 }
#podcast-url-container { text-align: center;background: white }
#podcast-url-container { height: 40px }
#text-container { text-align: left }
#text-container *  {display: block}
#text-container label { float:left; width: 70px; clear: both }
#text-container div { margin-left: 70px;}
#text-container input { width: 100%; margin-bottom: 1em }
.box {margin-bottom: 0}
#custom-time { 
  display: none; 
  background: #D0D3CE; 
  margin: 0 auto 1em auto;
  padding: 0.25em; 
  text-align: center; 
  width: 97%;
  border-radius: 5px;
}
#rss-img {
  width: 48px;
}
#rss-header {
  margin-left: 48px;
}
#duration a { line-height: 1.7em;padding: 0.5em 0}
#custom-time input { width: 48%; background: white }
#err, #thanks, #station, #station-preselect { display: none }
#err, #thanks { position: relative; top: 0; left: 0; line-height: 1.25em }

label { font-size: 0.8em; line-height: 1.3em }

@media screen and (max-width: 736px) {
  .feature .content {
    padding: 2em 0.5em !important;
  }
}
</style>
<div id="main">
  <h1>Indycast Reminders<br/>Listen later to what's on now</h1>

  <div class="box alt container">
    <section class="feature left">
      <div class="content">

        <label for="duration">What period?</label>

        <ul class="week-group group" id="duration">
          <li><a data="-30" class="button">Last<br/>half hour</a></li>
          <li><a data="30" class="button">Current<br/>half hour</a></li>
          <li><a data="60" class="button">Current<br/>hour</a></li>
        </ul>

        <div id="custom-time">
          <input id="start_time" type="text" placeholder="start time">
          <input id="end_time" type="text" placeholder="end time">
        </div>

        <label for="station">What station?</label>
        <div id="station-preselect"></div>
        <ul class="radio-group group" id="station"><?php
          foreach(active_stations() as $station) {
            echo '<li><a desc="' . $station['description'] . '" class="button">' . ($station['callsign']) . '</a></li>';
          }
        ?></ul>
      </div>
      <div class="content">
        <div id="text-container">

          <label id='email-label' for="email">Your Email</label>
          <div>
            <input id='email-input' type='email' name='email'>
          </div>

          <label for="notes">Show Notes</label>
          <div>
            <input type='text' name='notes' placeholder="To help remember what this is">
          </div>
        </div>
        <div id='podcast-url-container'>
          <div id="thanks">Thanks, we'll notify you when the show is over and ready for download.</div>
          <div id="err">Woops, unable to register this reminder. Please try again. If the problem persists, <a href=mailto:indycast@googlegroups.com>Email us</a> with details.</div>
          <a class='big-button disabled'>
            <span id='rss-top'>
              <div id='rss-img'>
                <i class="fa fa-envelope"></i>
              </div>
              <div id='rss-header'>
                <h3 id='rss-title'>Email me the MP3</h3>
              </div>
            </span>
          </a>
        </div>
      </div>
    </section>
  </div>
</div>
<div id="footer">
  <div class="container 75%">

    <header class="major last">
      <h2>About</h2>
    </header>

    <div style="text-align: left">
      <p>Listening to something right now but have to run and don't have the time to finish it? Miss the beginning of something and want to catch it later?</p>
      <h3>We'll send you a reminder with a link to the audio. (For free of course)</h3>

      <p>You can even leave notes for your future-self telling yourself why you think it's so awesome.</p>
      <p>Later on, when the show is over, an email will be sent to you with a link and the notes you leave.</p>

      <p><b>Privacy policy:</b> We don't collect email addresses and we delete everything from our database after we send the email off to you.  Don't worry, we're on your side!</p>
    </div>
    <ul class="icons">
      <li><a href="https://twitter.com/indycaster" class="icon fa-twitter"><span class="label">Twitter</span></a></li>
      <li><a href="http://github.com/kristopolous/DRR/" class="icon fa-github"><span class="label">Github</span></a></li>
    </ul>

    <ul class="copyright">
      <li>This is an <a href="https://github.com/kristopolous/DRR">open source project</a>.</li><li>Design: <a href="http://html5up.net">HTML5 UP</a></li>
    </ul>
  </div>
</div>
<script src='//cdnjs.cloudflare.com/ajax/libs/underscore.js/1.8.3/underscore-min.js'></script>
<script src="//code.jquery.com/jquery-1.11.3.min.js"></script>
<script src="/assets/js/evda.min.js"></script>
<!--[if lte IE 8]><script src="/assets/js/ie/respond.min.js"></script><![endif]-->
<script>
function ls(key, value) {
  if (arguments.length == 1) {
    return localStorage[key] || false;
  } else {
    localStorage[key] = value;
  }
  return value;
}

function easy_bind(list) {
  _.each(list, function(what) {

    var node = document.querySelector('#' + what);

    if(!node) {
      node = document.querySelector('input[name="' + what + '"]');
      if(!node) {
        throw new Error("Can't find anything matching ", what);
      }
    }

    if(node.nodeName == 'INPUT') {

      $(node).on('blur focus change keyup', function() {
        ev(what, this.value, {node: this});
      });

      ev(what, function(val){ 
        node.value = val; 
      });

    } else {
      $("a", node).on(listenEvent, function(){
        // This tricks stupid iDevices into not fucking around and screwing with the user.
        // (Requiring a user to tap twice to select anything.  WTF apple...)
        var mthis = this;

        setTimeout(function(){
          ev(what, mthis.getAttribute('data') || mthis.innerHTML);
        }, 0);
      });

      ev(what, function(val) {
        $("a", node).removeClass('selected');
        $("a:contains(" + val + ")", node).addClass("selected");
        $("a[data='" + val + "']", node).addClass("selected");
      });
    }
    ev.fire(what); 
  });
}

function easy_sync(list) {
  _.each(list, function(what) {
    if(ls(what)) {
      ev(what, ls(what));
    } 
    ev.after(what, function(value) {
      ls(what, value);
    });
  });
  return ev('');
}


//
// 2 range suggestions 30 min, 1 hr are always offered.
// the 1 hour is always the current hour and the 30 minute
// is always the nearest 30 minute that is the present
//
// The most laborious invocation appears to be our best friend here.
// That's this one, from mdn:
//
// new Date(year, month[, day[, hour[, minutes[, seconds[, milliseconds]]]]]);
//
var
  isiDevice = navigator.userAgent.match(/ip(hone|od|ad)/i),
  listenEvent = isiDevice ? 'touchend' : 'click',
  ev = EvDa({
    // find out the local tz offset
    offset: (new Date()).getTimezoneOffset(), 
    start_time: '', 
    end_time: '', 
    duration: '30', 
    email: '', 
    notes: ''
  }),

  right_now = new Date(),

  current_hour = {
    human_time: 'the current hour',
    start_time: +date_diff(right_now, {minutes: 0}) / 1000,
    end_time: +date_diff(right_now, {minutes: 0, hours: "+1"}) / 1000
  },
  
  last_half_hour = {
    human_time: 'the previous half hour',
    start_time: +date_diff(right_now, {minutes: "% 30 - 30 - (ts.getMinutes() % 30)"}) / 1000,
    end_time: +date_diff(right_now, {minutes: "% 30 - (ts.getMinutes() % 30)"}) / 1000
  }

  current_half_hour = {
    human_time: 'the current half hour',
    start_time: +date_diff(right_now, {minutes: "% 30 - (ts.getMinutes() % 30)"}) / 1000,
    end_time: +date_diff(right_now, {minutes: "% 30 + 30 - (ts.getMinutes() % 30)"}) / 1000
  }

ev.after('', function(map) {
  if(map.email && map.station && map.start_time && map.end_time) {
    $(".big-button").removeClass('disabled');
  } else {
    $(".big-button").addClass('disabled');
  }
});

$(function(){

  ev('duration', function(what) {
    if(what == '30') {
      ev(current_half_hour);
    } else if (what == '60') {
      ev(current_hour);
    } else if (what == '-30') {
      ev(last_half_hour);
    }
  });

  easy_bind(['email', 'notes', 'station', 'duration', 'start_time', 'end_time']);

  ev({
    duration: '30',
  });

  var what = easy_sync(['email', 'station', 'duration']);

  if(what.station) {
    $("#station-preselect")
      .html("Auto-selected from previous use: <b>" + what.station.toUpperCase() + "</b><br/>")
      .append($("<a>Select a different station</a>").click(station_select))
      .show()

  } else {
    station_select();
  } 

  $(".big-button").click(function(){
    if($(this).hasClass('disabled')) {
      return;
    }
    if(ev('duration') == 'custom') {
      ev('human_time', 'from ' + ev('start_time') + ' to ' + ev('end_time'));
    }

    $.post('/api/reminder', ev(''), function(res) {
      $('.big-button').slideUp();
      if(res != 'true') {
        $("#err").slideDown();
      } else {
        $("#thanks").slideDown();
      }
    });
  });

});

ev('duration', function(what, meta) {
  if(what == 'custom') {
    $("#custom-time").slideDown();
  } else if (meta.old == 'custom') {
    $("#custom-time").slideUp();
  }
});

</script>
