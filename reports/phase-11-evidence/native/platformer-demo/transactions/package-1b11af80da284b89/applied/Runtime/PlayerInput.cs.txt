using UnityEngine;
using UnityEngine.InputSystem;
using System;

namespace PolyForge
{
    public interface IPlayerInput
    {
        Vector2 Movement {get;}
        bool ConsumeRestart();
    }
    public sealed class KeyboardPlayerInput : IPlayerInput, IDisposable
    {
        int lastRestartFrame=-1;
        bool restartQueued;
        public KeyboardPlayerInput(){InputSystem.onAfterUpdate+=PollRestart;}
        void PollRestart()
        {
            var k=Keyboard.current;
            if(k!=null && k.rKey.wasPressedThisFrame && lastRestartFrame!=Time.frameCount)
            {lastRestartFrame=Time.frameCount;restartQueued=true;}
        }
        public void Dispose(){InputSystem.onAfterUpdate-=PollRestart;}
        public Vector2 Movement
        {
            get
            {
                var k=Keyboard.current;if(k==null)return Vector2.zero;
                return Vector2.ClampMagnitude(new Vector2((k.dKey.isPressed?1:0)-(k.aKey.isPressed?1:0),(k.wKey.isPressed?1:0)-(k.sKey.isPressed?1:0)),1);
            }
        }
        public bool ConsumeRestart()
        {
            bool value=restartQueued;restartQueued=false;return value;
        }
    }
}
