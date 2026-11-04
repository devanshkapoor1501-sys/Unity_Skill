using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace PolyForge
{
    public interface IPlatformerInput : IPlayerInput { bool ConsumeJump(); }
    public sealed class KeyboardPlatformerInput : IPlatformerInput, IDisposable
    {
        readonly KeyboardPlayerInput keyboard = new KeyboardPlayerInput();
        bool jump;
        int lastFrame = -1;
        public KeyboardPlatformerInput() { InputSystem.onAfterUpdate += Poll; }
        void Poll()
        {
            var k = Keyboard.current;
            if (k != null && k.spaceKey.wasPressedThisFrame && lastFrame != Time.frameCount)
            { lastFrame = Time.frameCount; jump = true; }
        }
        public Vector2 Movement => keyboard.Movement;
        public bool ConsumeRestart() => keyboard.ConsumeRestart();
        public bool ConsumeJump() { bool value = jump; jump = false; return value; }
        public void Dispose() { InputSystem.onAfterUpdate -= Poll; keyboard.Dispose(); }
    }
}
