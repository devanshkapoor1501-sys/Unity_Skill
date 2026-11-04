using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using System;

namespace PolyForge.Animation.Editor.Tests
{
    public class AnimationTests
    {
        const string Model="Assets/PolyForgeGenerated/Animation/robot.fbx";
        const string Prefab="Assets/PolyForgeGenerated/Animation/Robot.prefab";
        const string Controller="Assets/PolyForgeGenerated/Animation/Robot.controller";
        [Test] public void ImportedRigHasTwoLoopingClipsAndNativeSkinBindings()
        {
            var source=AssetDatabase.LoadAssetAtPath<GameObject>(Model);
            Assert.That(source,Is.Not.Null,"Animation model has not been built");
            var clips=AssetDatabase.LoadAllAssetsAtPath(Model).OfType<AnimationClip>().Where(c=>!c.name.StartsWith("__preview__")).ToArray();
            Assert.That(clips.Count(c=>c.name.EndsWith("Idle")),Is.EqualTo(1));
            Assert.That(clips.Count(c=>c.name.EndsWith("Walk")),Is.EqualTo(1));
            foreach(var c in clips){Assert.That(c.length,Is.EqualTo(1).Within(.05));Assert.That(c.isLooping,Is.True);}
            Assert.That(source.GetComponentsInChildren<SkinnedMeshRenderer>().Length,Is.GreaterThan(10));
        }
        [Test] public void AnimatorGraphHasBothTransitionsAndInPlaceRootPolicy()
        {
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(Prefab);Assert.That(prefab,Is.Not.Null);
            var animator=prefab.GetComponent<Animator>();Assert.That(animator,Is.Not.Null);Assert.That(animator.applyRootMotion,Is.False);
            var c=AssetDatabase.LoadAssetAtPath<AnimatorController>(Controller);Assert.That(c,Is.Not.Null);
            var states=c.layers[0].stateMachine.states.Select(s=>s.state).ToArray();
            Assert.That(states.Select(s=>s.name),Is.EquivalentTo(new[]{"Idle","Walk"}));
            foreach(var state in states)Assert.That(state.transitions.Any(t=>t.destinationState!=null && t.destinationState!=state),Is.True);
        }
        [Test] public void WrongBoneMappingIsRejected()
        {
            var clone=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Prefab));
            try
            {
                var skin=clone.GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name.EndsWith(":module:thigh_l"));
                var bones=skin.bones;int left=Array.FindIndex(bones,b=>b!=null && b.name=="thigh_l");int right=Array.FindIndex(bones,b=>b!=null && b.name=="thigh_r");
                Assert.That(left,Is.GreaterThanOrEqualTo(0));Assert.That(right,Is.GreaterThanOrEqualTo(0));bones[left]=bones[right];skin.bones=bones;
                Assert.Throws<InvalidOperationException>(()=>PolyForge.Animation.Editor.AnimationInspector.Verify(clone,AssetDatabase.LoadAssetAtPath<AnimatorController>(Controller)));
            }
            finally{UnityEngine.Object.DestroyImmediate(clone);}
        }
        [Test] public void DisconnectedLimbIsRejected()
        {
            var clone=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(Prefab));Mesh mesh=null;
            try
            {
                var skin=clone.GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name.EndsWith(":module:thigh_l"));
                mesh=UnityEngine.Object.Instantiate(skin.sharedMesh);mesh.boneWeights=new BoneWeight[mesh.vertexCount];skin.sharedMesh=mesh;
                Assert.Throws<InvalidOperationException>(()=>PolyForge.Animation.Editor.AnimationInspector.Verify(clone,AssetDatabase.LoadAssetAtPath<AnimatorController>(Controller)));
            }
            finally{UnityEngine.Object.DestroyImmediate(clone);if(mesh!=null)UnityEngine.Object.DestroyImmediate(mesh);}
        }
        [Test] public void MissingTransitionIsRejected()
        {
            var controller=new AnimatorController();controller.AddLayer("Base");var machine=controller.layers[0].stateMachine;
            var clips=AssetDatabase.LoadAllAssetsAtPath(Model).OfType<AnimationClip>().Where(c=>!c.name.StartsWith("__preview__")).ToArray();
            machine.AddState("Idle").motion=clips.Single(c=>c.name.EndsWith("Idle"));machine.AddState("Walk").motion=clips.Single(c=>c.name.EndsWith("Walk"));
            try{Assert.Throws<InvalidOperationException>(()=>PolyForge.Animation.Editor.AnimationInspector.Verify(AssetDatabase.LoadAssetAtPath<GameObject>(Prefab),controller));}
            finally{UnityEngine.Object.DestroyImmediate(controller);}
        }
    }
}
