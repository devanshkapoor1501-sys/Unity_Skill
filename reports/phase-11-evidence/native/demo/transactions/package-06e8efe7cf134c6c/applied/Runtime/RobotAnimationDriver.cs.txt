using UnityEngine;

namespace PolyForge
{
    [RequireComponent(typeof(Animator))]
    public sealed class RobotAnimationDriver : MonoBehaviour
    {
        public PatrolEnemy enemy;
        Animator animator;
        void Awake(){animator=GetComponent<Animator>();animator.applyRootMotion=false;}
        void Update()
        {
            bool walking=enemy!=null && enemy.session!=null && enemy.session.State=="RUNNING" && enemy.speed>0;
            animator.SetBool("Walking",walking);
        }
    }
}
