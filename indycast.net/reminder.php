<?php 
include_once('common.php'); 
?>
<!DOCTYPE HTML>
<html>
  <head>
    <title>Indycast Reminders</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <!--[if lte IE 8]><script src="/assets/js/ie/html5shiv.js"></script><![endif]-->
    <link rel="stylesheet" href="/assets/css/main.css" />
    <!--[if lte IE 8]><link rel="stylesheet" href="/assets/css/ie8.css" /><![endif]-->
    <meta name="description" content="Sending you audio for later enjoyment" />
    <meta property="og:site_name" content="Indycast" />
    <link href='http://fonts.googleapis.com/css?family=Inconsolata' rel='stylesheet' type='text/css'>
    <link href='http://fonts.googleapis.com/css?family=Lora' rel='stylesheet' type='text/css'>
    <style>
    h1 { background: white } 
    #duration { width: 100 %}
    #duration li { width: 32% }
    #rss-img { font-size: 40px; width: 48px; min-height: auto; height: auto }
    #rss-header { margin-left: 54px ; min-height: auto; margin-top: 3px}
    #podcast-done { display: block }
    #podcast-url { line-height: 0 }
    #podcast-url-container { text-align: center;background: white }
    @media screen and (max-width: 736px) {
      .feature .content {
        padding: 2em 0.5em !important;
      }
    }
    #podcast-url h3 { font-size: 1.3em }
    #text-container { text-align: left }
    #text-container *  {display: block}
    #text-container label { float:left; width: 70px;clear: both }
    #text-container div { margin-left: 70px;}
    #text-container input {width: 100%;margin-bottom: 1em }
    .box {margin-bottom: 0}
    
    label { font-size: 0.8em}
    </style>
  </head>
  <body>
    <div id="main">
      <h1>Set a Reminder</h1>

      <div class="box alt container">
        <section class="feature left">
          <div class="content">

            <label for="duration">What period?</label>
            <ul class="week-group group" id="duration">
              <li><a data="30" class="button">Current &frac12;hr</a></li>
              <li><a data="1hr" class="button">Current hr</a></li>
              <li><a data="1hr30" class="button">Custom</a></li>
            </ul>
            <label for="station">What station?</label>
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
                <input type='text' name='notes'>
              </div>
            </div>
            <div id='podcast-url-container'>
              <a class='big-button'>
                <span id='rss-top'>
                  <div id='rss-img'>
                    <i class="fa fa-envelope"></i>
                  </div>
                  <div id='rss-header'>
                    <h3 id='rss-title'>Email me a reminder</h3>
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
          <p>Listening to something right now but have to run and don't have the time to finish it?</p>
          <p>Miss the beginning of something and want to catch it later?</p>
          <h3>We'll send you a reminder with a link to the audio. For free of course.</h3>

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
  </body>
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

  //
  // This is a python inspired way of doing things.
  // change_map has datetime.timedelta syntax and operates
  // 
  //  as an override if it's an integer
  //  as an eval if it's a string (such as +1 or -1)
  //
  // Currently all we care about are 
  // hours and minutes.
  //
  // seconds and milliseconds are zeroed for us.
  //
  // It can be empty of course.
  //
  function date_diff(ts, change_map) {

    change_map = change_map || {};

    if( !('hours' in change_map) ) {
      change_map['hours'] = ts.getHours();
    } else if (change_map.hours.length) {
      // oh noes! The spirit of Douglas Crockford has now cursed my family!
      eval("change_map['hours'] = ts.getHours() " + change_map['hours']);
    }

    if( !('minutes' in change_map) ) {
      change_map['minutes'] = ts.getMinutes();
    } else if (change_map.minutes.length) {
      eval("change_map['minutes'] = ts.getMinutes() " + change_map['minutes']);
    }

    return new Date(
      ts.getFullYear(),
      ts.getMonth(),
      ts.getDay(),
      change_map.hours,
      change_map.minutes,
      0,
      0
    );
  }
    
  function easy_bind(map) {
    if(_.isArray(map)) {
      _.each(map, function(what) {
        var node = document.querySelector('#' + what);
        if(!node) {
          node = document.querySelector('input[name="' + what + '"]');
          if(!node) {
            throw new Error("Can't find anything matching ", what);
          }
        }
        $(node).on('blur focus change keyup', function() {
          ev(what, this.value, {node: this});
        });
      });
    }
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
    email = ls('email'),
    ev = EvDa({start_time: '', end_time: '', station: '', email: '', notes: ''}),
    last_station = ls('last'),
    right_now = new Date(),
    current_hour = [
      date_diff(right_now, {minutes: 0}),
      date_diff(right_now, {minutes: 0, hours: "+1"})
    ],
    current_half_hour = [
      date_diff(right_now, {minutes: "% 30 - (ts.getMinutes() % 30)"}),
      date_diff(right_now, {minutes: "% 30 + 30 - (ts.getMinutes() % 30)"})
    ]

  console.log(current_hour, current_half_hour);  

  $(function(){

    $("#start,#name").bind('blur focus change keyup',function(){
      ev(this.id, this.value, {node: this});
    });
    $(".big-button").click(function(){
    });

  });

  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

  ga('create', 'UA-28399789-2', 'auto');
  ga('send', 'pageview');
  </script>
</html>
