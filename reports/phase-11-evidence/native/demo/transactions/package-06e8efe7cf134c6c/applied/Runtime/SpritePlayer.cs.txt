using UnityEngine;

namespace PolyForge
{
    [RequireComponent(typeof(Rigidbody2D),typeof(BoxCollider2D))]
    public sealed class SpritePlayer:MonoBehaviour
    {
        public float speed=3;
        IPlayerInput input;
        public IPlayerInput Input
        {
            get=>input;
            set{if(ReferenceEquals(input,value))return;(input as System.IDisposable)?.Dispose();input=value;}
        }
        Rigidbody2D body;
        void Awake(){body=GetComponent<Rigidbody2D>();Input=new KeyboardPlayerInput();}
        void FixedUpdate(){body.linearVelocity=Vector2.ClampMagnitude(Input?.Movement??Vector2.zero,1)*speed;}
        void OnDestroy(){Input=null;}
    }
}
