# Shotlist schema V2 (episode_shotlist.json)
{"episode":"id","res":[1920,1080],"samples":8,"audio":{"bgm":"auto","bgm_db":-21},
 "shots":[{"id":"s01","dur":4.0,"set":"western_street","mood":"golden",
  "subject_zone":"left_third|center|right_third","ui_safe_zone":"right_third|top_left|none",
  "cast":[{"actor":"maya","at":"A|Entry|standing|sitting_sofa|walking_path|[x,y,z]","face":"dan|B","rot":deg,
           "action":"talk_emphatic" | "actions":[[0,"talk_calm"],[2.4,"argue_point"]],   // upper-body acting; base idle/walk/sit is automatic
           "path":[{"t":2.9,"to":"A"}],"emote":"happy" | "emotes":[[0,"neutral"],[1.2,"surprised"]],
           "look":"cam|dan|[x,y,z]","lines":[{"say":"text","voice":"Zira","t":0.3,"rate":0}]}],
  "cam":{"preset":"Wide|Medium|SlowDolly|Handheld|LowHero","focus":["maya","dan"]}
        | {"preset":"OTS","over":"dan","at":"maya"} | {"preset":"CloseUp","focus":["dan"],"flip":-1},
  "callouts":[{"t":1.2,"dur":2.4,"type":"card|icon|stat|bars|kinetic|lower","text":".."}]}]}   // NO x/y on callouts
Base clips you may name in `actions` too: idle walk run wave sit_idle sit_talk mx_<mixamo name>.
Upper-body actions: talk_calm talk_emphatic argue_point surprised slump_tired think_chin drink_coffee shrug laugh cross_arms phone_scroll.
Callout fields: card{kicker,text,sub,color} icon{icon,color} stat{value,suffix,text} bars{text,data:[[label,val,color]]} kinetic{text,size} lower{text,sub}
