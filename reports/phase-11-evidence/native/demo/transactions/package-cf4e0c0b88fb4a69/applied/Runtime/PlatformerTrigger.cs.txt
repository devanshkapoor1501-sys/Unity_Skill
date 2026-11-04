using UnityEngine;

namespace PolyForge
{
    [RequireComponent(typeof(BoxCollider2D))]
    public sealed class PlatformerTrigger : MonoBehaviour
    {
        public enum Kind { Checkpoint, Hazard, Goal }
        public Kind kind;
        public PlatformerSession session;
        public PlatformerPlayer actor;
        public int damage = 1;
        void OnTriggerEnter2D(Collider2D other)
        {
            if (actor != null && session != null && other.GetComponent<PlatformerPlayer>() == actor)
                session.Touch(kind, damage);
        }
    }
}
