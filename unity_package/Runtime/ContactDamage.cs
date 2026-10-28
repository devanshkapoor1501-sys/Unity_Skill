using UnityEngine;

namespace PolyForge
{
    public sealed class ContactDamage : MonoBehaviour
    {
        public ArenaSession session;
        public int amount=25;
        public float cooldownSeconds=.5f;
        float nextAllowed;
        public void ResetContact(){nextAllowed=0;}
        void OnTriggerStay(Collider other)
        {
            if(session==null || session.State!="RUNNING" || session.ElapsedSeconds<nextAllowed)return;
            var player=other.GetComponentInParent<PlayerController>();
            if(player==null || player!=session.player)return;
            player.Health.Damage(amount);nextAllowed=session.ElapsedSeconds+cooldownSeconds;
            session.Record("damage",gameObject.name,amount);
            if(player.Health.Current==0)session.Fail();
        }
    }
}
