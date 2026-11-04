using UnityEngine;

namespace PolyForge
{
    public sealed class PlatformerHud : MonoBehaviour
    {
        public PlatformerSession session;
        void OnGUI()
        {
            if (session == null || session.player == null) return;
            GUI.color = Color.white;
            GUI.Box(new Rect(12, 12, 600, 78), "CHECKPOINT CROSSING\nA / D move    Space jump    R restart\nLives: "
                + session.player.Health.Current + "    Checkpoint: " + session.Checkpoint + "    " + session.State
                + "    Reach the green finish flag");
        }
    }
}
