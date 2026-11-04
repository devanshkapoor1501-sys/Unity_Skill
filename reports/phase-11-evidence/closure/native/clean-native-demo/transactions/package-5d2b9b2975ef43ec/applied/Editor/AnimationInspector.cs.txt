using System;
using System.Linq;
using UnityEditor.Animations;
using UnityEngine;

namespace PolyForge.Animation.Editor
{
    public static class AnimationInspector
    {
        public static void Verify(GameObject candidate,AnimatorController controller)
        {
            if(candidate==null || controller==null)throw new InvalidOperationException("Missing animated candidate/controller");
            var states=controller.layers[0].stateMachine.states.Select(s=>s.state).ToArray();
            if(states.Length!=2 || !states.Any(s=>s.name=="Idle") || !states.Any(s=>s.name=="Walk"))throw new InvalidOperationException("Missing Idle/Walk states");
            foreach(var state in states)
                if(state.motion==null || !state.transitions.Any(t=>t.destinationState!=null && t.destinationState!=state))throw new InvalidOperationException("Missing animation transition/motion");
            var skins=candidate.GetComponentsInChildren<SkinnedMeshRenderer>();
            if(skins.Length<10)throw new InvalidOperationException("Disconnected/missing mechanical skin");
            foreach(var skin in skins)
            {
                const string marker=":module:";int index=skin.name.IndexOf(marker,StringComparison.Ordinal);
                if(index<0)throw new InvalidOperationException("Missing module semantic ID");
                string expected=skin.name.Substring(index+marker.Length);
                if(skin.sharedMesh==null || skin.sharedMesh.boneWeights.Length!=skin.sharedMesh.vertexCount)throw new InvalidOperationException("Missing vertex weights");
                foreach(var weight in skin.sharedMesh.boneWeights)
                    if(weight.weight0<.999f || weight.boneIndex0>=skin.bones.Length || skin.bones[weight.boneIndex0]==null || skin.bones[weight.boneIndex0].name!=expected)
                        throw new InvalidOperationException("Wrong bone mapping or detached weighted limb: "+expected);
            }
        }
    }
}
