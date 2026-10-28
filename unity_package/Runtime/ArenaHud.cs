using UnityEngine;

namespace PolyForge
{
    public sealed class ArenaHud : MonoBehaviour
    {
        public ArenaSession session;
        GUIStyle label;
        void OnGUI()
        {
            if(session==null || session.player==null)return;
            if(label==null)label=new GUIStyle(GUI.skin.label){fontSize=20};
            GUI.Box(new Rect(16,16,340,136),"");
            GUI.Label(new Rect(30,26,320,28),"Health: "+session.player.Health.Current+" / 100",label);
            GUI.Label(new Rect(30,56,320,28),"Survive: "+Mathf.Max(0,30-session.ElapsedSeconds).ToString("0.0")+"s",label);
            GUI.Label(new Rect(30,86,320,28),"WASD move  |  R restart",label);
            var message=session.State=="WON"?"You survived! Press R to restart.":session.State=="FAILED"?"Defeated. Press R to restart.":"Stay alive for 30 seconds.";
            GUI.Label(new Rect(30,116,700,30),message,label);
            if(Camera.main!=null)
            {
                var p=Camera.main.WorldToScreenPoint(session.player.transform.position+Vector3.up*2.2f);
                GUI.Label(new Rect(p.x-25,Screen.height-p.y,100,30),"YOU",label);
            }
        }
    }
}
