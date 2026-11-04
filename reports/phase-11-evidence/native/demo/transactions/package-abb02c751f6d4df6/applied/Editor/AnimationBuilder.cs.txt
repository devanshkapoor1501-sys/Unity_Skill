using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using PolyForge.Editor;
using System.Security.Cryptography;

namespace PolyForge.Animation.Editor
{
    [Serializable] public class AnimationInput
    {
        public string candidate_digest;public string input_digest;
        public string model_path;public string asset_id;public string expected_fbx_sha256;
    }
    [Serializable] public class AnimationFile {public string path;public string sha256;}
    [Serializable] public class AnimationReport
    {
        public string status="PASS";public string candidate_digest;public string unity_version;
        public string model_guid;public string prefab_guid;public string scene_guid;
        public string[] clips;public string[] bone_names;public int enemy_count;
        public AnimationFile[] output_files;
    }
    public static class AnimationBuilder
    {
        public const string Folder="Assets/PolyForgeGenerated/Animation";
        public const string ScenePath=Folder+"/AnimationArena.unity";
        static string Hash(string path){using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();}
        public static void BuildBatch()
        {
            try
            {
                var job=JsonUtility.FromJson<AnimationInput>(File.ReadAllText(PolyForgeBuilder.Argument("-polyforgeGameInput")));
                if(Hash(job.model_path)!=job.expected_fbx_sha256)throw new Exception("Imported FBX differs from the approved source digest");
                AssetDatabase.ImportAsset(job.model_path,ImportAssetOptions.ForceSynchronousImport);
                var importer=(ModelImporter)AssetImporter.GetAtPath(job.model_path);
                importer.animationType=ModelImporterAnimationType.Generic;importer.importAnimation=true;
                importer.optimizeGameObjects=false;importer.globalScale=1;importer.useFileScale=true;
                importer.materialImportMode=ModelImporterMaterialImportMode.None;
                var definitions=importer.defaultClipAnimations;
                if(definitions.Length!=2)throw new Exception("Expected exactly two exported slotted actions");
                foreach(var clip in definitions){clip.loopTime=true;clip.lockRootPositionXZ=true;clip.lockRootHeightY=true;clip.lockRootRotation=true;}
                importer.clipAnimations=definitions;importer.SaveAndReimport();
                var source=AssetDatabase.LoadAssetAtPath<GameObject>(job.model_path);
                var clips=AssetDatabase.LoadAllAssetsAtPath(job.model_path).OfType<AnimationClip>().Where(c=>!c.name.StartsWith("__preview__")).ToArray();
                AnimationClip Find(string name)=>clips.Single(c=>c.name.EndsWith(name,StringComparison.Ordinal));
                var controller=AssetDatabase.LoadAssetAtPath<AnimatorController>(Folder+"/Robot.controller");
                if(controller==null)controller=AnimatorController.CreateAnimatorControllerAtPath(Folder+"/Robot.controller");
                var machine=controller.layers[0].stateMachine;
                foreach(var state in machine.states)machine.RemoveState(state.state);
                foreach(var p in controller.parameters)controller.RemoveParameter(p);
                controller.AddParameter("Walking",AnimatorControllerParameterType.Bool);
                var idle=machine.AddState("Idle");idle.motion=Find("Idle");var walk=machine.AddState("Walk");walk.motion=Find("Walk");machine.defaultState=idle;
                var forward=idle.AddTransition(walk);forward.hasExitTime=false;forward.duration=.05f;forward.AddCondition(AnimatorConditionMode.If,0,"Walking");
                var back=walk.AddTransition(idle);back.hasExitTime=false;back.duration=.05f;back.AddCondition(AnimatorConditionMode.IfNot,0,"Walking");
                var prefab=(GameObject)PrefabUtility.InstantiatePrefab(source);prefab.name=job.asset_id+"_animated";
                var animator=prefab.GetComponent<Animator>();if(animator==null)animator=prefab.AddComponent<Animator>();
                animator.runtimeAnimatorController=controller;animator.applyRootMotion=false;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
                prefab.AddComponent<RobotAnimationDriver>();
                AnimationInspector.Verify(prefab,controller);
                var material=AssetDatabase.LoadAssetAtPath<Material>(Folder+"/Robot.mat");
                if(material==null){material=new Material(Shader.Find("Universal Render Pipeline/Lit"));AssetDatabase.CreateAsset(material,Folder+"/Robot.mat");}
                material.SetColor("_BaseColor",new Color(.14f,.38f,.7f,1));
                foreach(var skin in prefab.GetComponentsInChildren<SkinnedMeshRenderer>())skin.sharedMaterials=Enumerable.Repeat(material,skin.sharedMaterials.Length).ToArray();
                PrefabUtility.SaveAsPrefabAsset(prefab,Folder+"/Robot.prefab");UnityEngine.Object.DestroyImmediate(prefab);
                var scene=EditorSceneManager.OpenScene("Assets/PolyForgeGenerated/Game/PlayableArena.unity",OpenSceneMode.Single);
                var session=UnityEngine.Object.FindFirstObjectByType<ArenaSession>();
                foreach(var enemy in session.enemies)
                {
                    foreach(var renderer in enemy.GetComponentsInChildren<MeshRenderer>())renderer.enabled=false;
                    var visual=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Folder+"/Robot.prefab"));
                    visual.transform.SetParent(enemy.transform,false);visual.transform.localScale=new Vector3(-1,1,1);
                    visual.GetComponent<RobotAnimationDriver>().enemy=enemy;
                }
                EditorSceneManager.SaveScene(scene,ScenePath);
                EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/PolyForgeGenerated/Game/PlayableArena.unity",true),new EditorBuildSettingsScene(ScenePath,true)};
                AssetDatabase.SaveAssets();
                var report=new AnimationReport{candidate_digest=job.candidate_digest,unity_version=Application.unityVersion,
                    model_guid=AssetDatabase.AssetPathToGUID(job.model_path),prefab_guid=AssetDatabase.AssetPathToGUID(Folder+"/Robot.prefab"),scene_guid=AssetDatabase.AssetPathToGUID(ScenePath),
                    clips=clips.Select(c=>c.name).ToArray(),bone_names=source.GetComponentsInChildren<Transform>().Select(t=>t.name).ToArray(),enemy_count=session.enemies.Length,
                    output_files=Directory.GetFiles(Folder,"*",SearchOption.AllDirectories).Select(p=>new AnimationFile{path=p.Replace('\\','/'),sha256=Hash(p)}).ToArray()};
                File.WriteAllText(PolyForgeBuilder.Argument("-polyforgeOutput"),JsonUtility.ToJson(report,true));EditorApplication.Exit(0);
            }
            catch(Exception e){Debug.LogException(e);EditorApplication.Exit(5);}
        }
    }
}
