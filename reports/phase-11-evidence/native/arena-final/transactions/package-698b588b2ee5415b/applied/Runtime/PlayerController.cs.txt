using UnityEngine;
using System;

namespace PolyForge
{
    [RequireComponent(typeof(CharacterController),typeof(Health))]
    public sealed class PlayerController : MonoBehaviour
    {
        public ArenaSession session;
        public float speed=4;
        IPlayerInput input;
        public IPlayerInput Input
        {
            get=>input;
            set{if(ReferenceEquals(input,value))return;(input as IDisposable)?.Dispose();input=value;}
        }
        public CharacterController Motor {get;private set;}
        public Health Health {get;private set;}
        float fallSpeed;
        void Awake(){Motor=GetComponent<CharacterController>();Health=GetComponent<Health>();Input=new KeyboardPlayerInput();}
        void FixedUpdate()
        {
            if(session==null || session.State!="RUNNING")return;
            var v=Vector2.ClampMagnitude(Input?.Movement??Vector2.zero,1);fallSpeed=Motor.isGrounded?-2:Mathf.Max(-30,fallSpeed+Physics.gravity.y*Time.fixedDeltaTime);
            Motor.Move(new Vector3(v.x*speed,fallSpeed,v.y*speed)*Time.fixedDeltaTime);
        }
        public void ResetAt(Vector3 position)
        {
            if(Motor==null)Motor=GetComponent<CharacterController>();
            if(Health==null)Health=GetComponent<Health>();
            Motor.enabled=false;transform.SetPositionAndRotation(position,Quaternion.identity);Motor.enabled=true;
            fallSpeed=0;Health.ResetHealth();Physics.SyncTransforms();
        }
        void OnDestroy(){Input=null;}
    }
}
