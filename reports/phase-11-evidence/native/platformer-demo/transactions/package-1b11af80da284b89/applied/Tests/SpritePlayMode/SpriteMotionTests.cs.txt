using System.Collections;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace PolyForge.Sprite.Tests
{
    public class SpriteMotionTests
    {
        sealed class Input:IPlayerInput{public Vector2 direction;public Vector2 Movement=>direction;public bool ConsumeRestart()=>false;}
        sealed class DisposableInput:IPlayerInput,System.IDisposable
        {
            public bool Disposed;public Vector2 Movement=>Vector2.zero;
            public bool ConsumeRestart()=>false;public void Dispose(){Disposed=true;}
        }
        [UnityTest] public IEnumerator DestroyedPlayerReleasesInputSubscription()
        {
            yield return SceneManager.LoadSceneAsync("SpriteArena");yield return null;
            var actor=Object.FindFirstObjectByType<SpritePlayer>();var input=new DisposableInput();actor.Input=input;
            Assert.That(input.Disposed,Is.False);Object.Destroy(actor.gameObject);yield return null;
            Assert.That(input.Disposed,Is.True);
        }
        [UnityTest] public IEnumerator LoopActuallyChangesImportedSpriteAndWraps()
        {
            yield return SceneManager.LoadSceneAsync("SpriteArena");yield return null;
            var actor=Object.FindFirstObjectByType<SpritePlayer>();var renderer=actor.GetComponent<SpriteRenderer>();
            var seen=new HashSet<string>();string first=null;bool returned=false;
            for(int i=0;i<90;i++){yield return new WaitForFixedUpdate();string name=renderer.sprite.name;if(first==null)first=name;else if(seen.Count>=6 && name==first)returned=true;seen.Add(name);}
            Assert.That(seen.Count,Is.EqualTo(6));Assert.That(returned,Is.True);
        }
        [UnityTest] public IEnumerator InjectedInputMovesAndReal2DWallStopsPlayer()
        {
            yield return SceneManager.LoadSceneAsync("SpriteArena");yield return null;
            var actor=Object.FindFirstObjectByType<SpritePlayer>();var input=new Input{direction=Vector2.right};actor.Input=input;var before=actor.transform.position;
            for(int i=0;i<100;i++)yield return new WaitForFixedUpdate();
            Assert.That(actor.transform.position.x,Is.GreaterThan(before.x+.5f));Assert.That(actor.transform.position.x,Is.LessThan(1.55f));
            Assert.That(actor.GetComponent<Rigidbody2D>().gravityScale,Is.Zero);
        }
        [UnityTest] public IEnumerator KeyboardWASDControlsThe2DFixture()
        {
            yield return SceneManager.LoadSceneAsync("SpriteArena");yield return null;
            var actor=Object.FindFirstObjectByType<SpritePlayer>();var old=InputSystem.settings.editorInputBehaviorInPlayMode;var background=InputSystem.settings.backgroundBehavior;
            Keyboard keyboard=null;
            try
            {
                InputSystem.settings.editorInputBehaviorInPlayMode=InputSettings.EditorInputBehaviorInPlayMode.AllDeviceInputAlwaysGoesToGameView;InputSystem.settings.backgroundBehavior=InputSettings.BackgroundBehavior.IgnoreFocus;
                keyboard=InputSystem.AddDevice<Keyboard>();
                actor.Input=new KeyboardPlayerInput();var start=actor.transform.position;
                InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.W));InputSystem.Update();Assert.That(actor.Input.Movement.y,Is.EqualTo(1),"Queued W must reach the real input adapter");for(int i=0;i<20;i++)yield return new WaitForFixedUpdate();
                Debug.Log("Sprite keyboard observed: device="+keyboard.deviceId+", current="+Keyboard.current?.deviceId+", W="+keyboard.wKey.isPressed+", movement="+actor.Input.Movement+", body="+actor.GetComponent<Rigidbody2D>().position);
                Assert.That(actor.transform.position.y,Is.GreaterThan(start.y+.4f));Assert.That(Mathf.Abs(actor.transform.position.z),Is.LessThan(.001f));
            }
            finally{if(keyboard!=null)InputSystem.RemoveDevice(keyboard);InputSystem.settings.editorInputBehaviorInPlayMode=old;InputSystem.settings.backgroundBehavior=background;}
        }
    }
}
