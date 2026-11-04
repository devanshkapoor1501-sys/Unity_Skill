using System;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;
using PolyForge.Sprite.Editor;

namespace PolyForge.Sprite.Editor.Tests
{
    public class SpriteTests
    {
        sealed class DisposableInput : IPlayerInput, IDisposable
        {
            public int Disposals;
            public Vector2 Movement=>Vector2.zero;
            public bool ConsumeRestart()=>false;
            public void Dispose(){Disposals++;}
        }
        [Test] public void ReplacingInputDisposesPreviousSubscription()
        {
            var actor=new GameObject("input ownership test");
            var first=new DisposableInput();var second=new DisposableInput();
            try
            {
                var player=actor.AddComponent<SpritePlayer>();player.Input=first;player.Input=second;
                Assert.That(first.Disposals,Is.EqualTo(1));player.Input=second;
                Assert.That(second.Disposals,Is.Zero);player.Input=null;
                Assert.That(second.Disposals,Is.EqualTo(1));
            }
            finally{if(actor!=null)UnityEngine.Object.DestroyImmediate(actor);}
        }
        [Test] public void ImportedSpritesKeepSixRectsPivotsAndStableIds()
        {
            var sprites=AssetDatabase.LoadAllAssetsAtPath(SpriteBuilder.AtlasPath).OfType<UnityEngine.Sprite>().OrderBy(s=>s.name).ToArray();
            Assert.That(sprites.Length,Is.EqualTo(6));
            for(int i=0;i<6;i++)
            {
                Assert.That(sprites[i].name,Is.EqualTo("frame-"+i));Assert.That(sprites[i].rect.width,Is.EqualTo(128));
                Assert.That(sprites[i].rect.x,Is.EqualTo(i*128));Assert.That(sprites[i].pivot.x,Is.EqualTo(64).Within(.01));
                Assert.That(sprites[i].pivot.y,Is.EqualTo(12.8f).Within(.01));Assert.That(sprites[i].pixelsPerUnit,Is.EqualTo(64));
                Assert.That(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprites[i],out string guid,out long id),Is.True);
                Assert.That(guid.Length,Is.EqualTo(32));Assert.That(id,Is.Not.Zero);
            }
        }
        [Test] public void FlipbookUsesActualSpriteReferencesAndOneSecondLoop()
        {
            var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(SpriteBuilder.Folder+"/Walk.anim");
            SpriteBuilder.VerifyClip(clip);Assert.That(clip.length,Is.EqualTo(1).Within(.001));Assert.That(clip.isLooping,Is.True);
        }
        [Test] public void MissingSpriteCurveIsRejected()
        {
            var clip=new AnimationClip();try{Assert.Throws<InvalidOperationException>(()=>SpriteBuilder.VerifyClip(clip));}finally{UnityEngine.Object.DestroyImmediate(clip);}
        }
        [Test] public void ReorderedSpriteReferenceCurveIsRejected()
        {
            var clip=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<AnimationClip>(SpriteBuilder.Folder+"/Walk.anim"));
            try
            {
                var binding=AnimationUtility.GetObjectReferenceCurveBindings(clip).Single();
                var keys=AnimationUtility.GetObjectReferenceCurve(clip,binding);var old=keys[0].value;keys[0].value=keys[1].value;keys[1].value=old;
                AnimationUtility.SetObjectReferenceCurve(clip,binding,keys);Assert.Throws<InvalidOperationException>(()=>SpriteBuilder.VerifyClip(clip));
            }
            finally{UnityEngine.Object.DestroyImmediate(clip);}
        }
    }
}
