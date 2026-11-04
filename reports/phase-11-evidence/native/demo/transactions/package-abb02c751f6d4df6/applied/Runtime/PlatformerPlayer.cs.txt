using UnityEngine;

namespace PolyForge
{
    [RequireComponent(typeof(Rigidbody2D), typeof(BoxCollider2D), typeof(Health))]
    public sealed class PlatformerPlayer : MonoBehaviour
    {
        public PlatformerSession session;
        public float speed = 4, jumpSpeed = 8, gravityScale = 2;
        public int groundLayer = 8;
        IPlatformerInput input;
        Rigidbody2D body;
        BoxCollider2D shape;
        public Rigidbody2D Body => body != null ? body : (body = GetComponent<Rigidbody2D>());
        public Health Health => GetComponent<Health>();
        public bool Grounded => (shape != null ? shape : (shape = GetComponent<BoxCollider2D>())).IsTouchingLayers(1 << groundLayer);
        public IPlatformerInput Input
        {
            get => input;
            set { if (ReferenceEquals(input, value)) return; (input as System.IDisposable)?.Dispose(); input = value; }
        }
        void Awake() { body = GetComponent<Rigidbody2D>(); shape = GetComponent<BoxCollider2D>(); Input = new KeyboardPlatformerInput(); }
        void FixedUpdate()
        {
            if (session == null) return;
            if (Input?.ConsumeRestart() == true) { session.Restart(); return; }
            bool jump = Input?.ConsumeJump() == true;
            if (session.State != "RUNNING") { Body.linearVelocity = Vector2.zero; Body.gravityScale = 0; return; }
            Body.gravityScale = gravityScale;
            var velocity = Body.linearVelocity;
            velocity.x = Mathf.Clamp(Input?.Movement.x ?? 0, -1, 1) * speed;
            if (jump && Grounded) velocity.y = jumpSpeed;
            Body.linearVelocity = velocity;
        }
        public void ResetAt(Vector3 position)
        {
            transform.position = position; Body.position = position;
            Body.linearVelocity = Vector2.zero; Body.angularVelocity = 0;
            Body.gravityScale = gravityScale; Physics2D.SyncTransforms();
        }
        void OnDestroy() { Input = null; }
    }
}
