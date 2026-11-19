# Shotlist schema (episode_shotlist.json)
{"episode":"id","res":[1920,1080],"samples":8,"audio":{"bgm":"auto","bgm_db":-21},
 "shots":[{"id":"s01","dur":4.0,"set":"cafe_street","mood":"golden",
  "cast":[{"actor":"maya","at":"A"|"Entry"|[x,y,z],"face":"B"|"dan","rot":deg,
           "action":"talk_emphatic" | "actions":[[0,"walk"],[2.9,"idle_breathe"]],
           "path":[{"t":2.9,"to":"A"}],"emote":"happy" | "emotes":[[0,"neutral"],[1.2,"surprised"]],
           "look":"cam"|"dan"|[x,y,z],"lines":[{"say":"text","voice":"Zira","t":0.3,"rate":0}]}],
  "cam":{"preset":"Wide|Medium|SlowDolly|Handheld|LowHero","focus":["maya","dan"]}
        | {"preset":"OTS","over":"dan","at":"maya"} | {"preset":"CloseUp","focus":"dan","flip":-1},
  "callouts":[{"t":1.2,"dur":2.4,"type":"card|icon|stat|bars|kinetic|lower","text":"..","x":1130,"y":150}]}]}
Callout fields: card{kicker,text,sub,color} icon{icon,color} stat{value,suffix,text} bars{text,data:[[label,val,color]]} kinetic{text,size} lower{text,sub}
