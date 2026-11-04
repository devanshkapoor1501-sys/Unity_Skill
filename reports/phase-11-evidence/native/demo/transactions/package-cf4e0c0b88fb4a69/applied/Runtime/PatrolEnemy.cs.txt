using UnityEngine;

namespace PolyForge
{
    [RequireComponent(typeof(Rigidbody))]
    public sealed class PatrolEnemy : MonoBehaviour
    {
        public ArenaSession session;
        public Vector3[] waypoints;
        public Vector3 spawn;
        public float speed=1.3f;
        Rigidbody body;
        int target;
        void Awake(){body=GetComponent<Rigidbody>();}
        void FixedUpdate()
        {
            if(session==null || session.State!="RUNNING" || waypoints==null || waypoints.Length==0)return;
            var next=Vector3.MoveTowards(body.position,waypoints[target],speed*Time.fixedDeltaTime);
            body.MovePosition(next);
            if(Vector3.Distance(next,waypoints[target])<.03f)target=(target+1)%waypoints.Length;
        }
        public void ResetPatrol()
        {
            if(body==null)body=GetComponent<Rigidbody>();
            body.position=spawn;body.rotation=Quaternion.identity;target=0;
            foreach(var contact in GetComponents<ContactDamage>())contact.ResetContact();
        }
    }
}
