using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEditor.U2D.Sprites;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace PolyForge.Sprite.Editor
{
    [Serializable] public class SpriteInput
    {
        public string asset_id;public string atlas_sha256;public string metadata_digest;public int frame_size;public int frame_count;public float pixels_per_unit;public float fps;public float[] pivot;
    }
    [Serializable] public class SpriteBinding{public string name;public string guid;public long local_id;public float x;public float width;public float height;public float pivot_x;public float pivot_y;}
    [Serializable] public class SpriteReport
    {
        public string status="PASS";public string unity_version;public string metadata_digest;public string atlas_sha256;public string prefab_guid;public string scene_guid;public string clip_guid;public float clip_seconds;public bool loop;public SpriteBinding[] sprites;
    }
    public static class SpriteBuilder
    {
        public const string Folder="Assets/PolyForgeGenerated/Sprites";
        public const string AtlasPath=Folder+"/atlas.png";
        public const string ScenePath=Folder+"/SpriteArena.unity";
        static string Hash(byte[] data){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
        static GUID SpriteId(string asset,int index){using(var md5=MD5.Create())return new GUID(BitConverter.ToString(md5.ComputeHash(Encoding.UTF8.GetBytes(asset+":sprite:"+index))).Replace("-","").ToLowerInvariant());}
        public static void VerifyClip(AnimationClip clip)
        {
            if(clip==null)throw new InvalidOperationException("Missing flipbook clip");
            var bindings=AnimationUtility.GetObjectReferenceCurveBindings(clip);
            if(bindings.Length!=1 || bindings[0].propertyName!="m_Sprite" || bindings[0].type!=typeof(SpriteRenderer) || bindings[0].path!="")throw new InvalidOperationException("Missing native SpriteRenderer reference curve");
            var keys=AnimationUtility.GetObjectReferenceCurve(clip,bindings[0]);
            if(keys.Length!=6 || !clip.isLooping || Mathf.Abs(clip.length-1)>.001f)throw new InvalidOperationException("Wrong flipbook timing/loop: keys="+keys.Length+", length="+clip.length+", isLooping="+clip.isLooping+", loopTime="+AnimationUtility.GetAnimationClipSettings(clip).loopTime+", stopTime="+AnimationUtility.GetAnimationClipSettings(clip).stopTime);
            for(int i=0;i<keys.Length;i++)if(keys[i].value==null || keys[i].value.name!="frame-"+(i%6) || Mathf.Abs(keys[i].time-i/6f)>.001f)throw new InvalidOperationException("Wrong sprite frame reference/order");
        }
        public static void BuildBatch()
        {
            try
            {
                var job=JsonUtility.FromJson<SpriteInput>(File.ReadAllText(PolyForge.Editor.PolyForgeBuilder.Argument("-polyforgeGameInput")));
                if(job.frame_size!=128 || job.frame_count!=6 || job.pixels_per_unit!=64 || job.fps!=6 || job.pivot.Length!=2 || job.pivot[0]!=.5f || job.pivot[1]!=.1f || Hash(File.ReadAllBytes(AtlasPath))!=job.atlas_sha256)throw new InvalidOperationException("Sprite source hash/metadata mismatch");
                AssetDatabase.ImportAsset(AtlasPath,ImportAssetOptions.ForceSynchronousImport);
                var importer=(TextureImporter)AssetImporter.GetAtPath(AtlasPath);importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Multiple;importer.spritePixelsPerUnit=64;importer.mipmapEnabled=false;importer.alphaIsTransparency=true;importer.textureCompression=TextureImporterCompression.Uncompressed;importer.filterMode=FilterMode.Point;importer.SaveAndReimport();
                var factory=new SpriteDataProviderFactories();factory.Init();var provider=factory.GetSpriteEditorDataProviderFromObject(importer);provider.InitSpriteEditorDataProvider();
                var rects=Enumerable.Range(0,6).Select(i=>new SpriteRect{name="frame-"+i,spriteID=SpriteId(job.asset_id,i),rect=new Rect(i*128,0,128,128),pivot=new Vector2(.5f,.1f),alignment=SpriteAlignment.Custom}).ToArray();
                provider.SetSpriteRects(rects);provider.GetDataProvider<ISpriteNameFileIdDataProvider>().SetNameFileIdPairs(rects.Select(r=>new SpriteNameFileIdPair(r.name,r.spriteID)));provider.Apply();importer.SaveAndReimport();
                var sprites=AssetDatabase.LoadAllAssetsAtPath(AtlasPath).OfType<UnityEngine.Sprite>().OrderBy(s=>s.name).ToArray();if(sprites.Length!=6)throw new Exception("Data Provider slicing did not import six sprites");
                var clip=AssetDatabase.LoadAssetAtPath<AnimationClip>(Folder+"/Walk.anim");if(clip==null){clip=new AnimationClip();AssetDatabase.CreateAsset(clip,Folder+"/Walk.anim");}clip.frameRate=6;clip.wrapMode=WrapMode.Loop;
                var settings=AnimationUtility.GetAnimationClipSettings(clip);settings.loopTime=true;AnimationUtility.SetAnimationClipSettings(clip,settings);
                // Native object-reference curves hold the final key for one frame: six keys give one second.
                AnimationUtility.SetObjectReferenceCurve(clip,EditorCurveBinding.PPtrCurve("",typeof(SpriteRenderer),"m_Sprite"),Enumerable.Range(0,6).Select(i=>new ObjectReferenceKeyframe{time=i/6f,value=sprites[i]}).ToArray());VerifyClip(clip);EditorUtility.SetDirty(clip);
                var controller=AssetDatabase.LoadAssetAtPath<AnimatorController>(Folder+"/Sprite.controller");if(controller==null)controller=AnimatorController.CreateAnimatorControllerAtPath(Folder+"/Sprite.controller");var machine=controller.layers[0].stateMachine;foreach(var state in machine.states)machine.RemoveState(state.state);var walk=machine.AddState("Walk");walk.motion=clip;machine.defaultState=walk;
                var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                var player=new GameObject(job.asset_id+"_2d");var renderer=player.AddComponent<SpriteRenderer>();renderer.sprite=sprites[0];renderer.sortingOrder=1;
                var body=player.AddComponent<Rigidbody2D>();body.gravityScale=0;body.freezeRotation=true;body.collisionDetectionMode=CollisionDetectionMode2D.Continuous;
                var collider=player.AddComponent<BoxCollider2D>();collider.size=new Vector2(.8f,1.6f);collider.offset=new Vector2(0,.8f);player.AddComponent<SpritePlayer>();var animator=player.AddComponent<Animator>();animator.runtimeAnimatorController=controller;animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
                PrefabUtility.SaveAsPrefabAsset(player,Folder+"/Robot2D.prefab");
                var wall=new GameObject("Wall2D");wall.transform.position=new Vector3(2,0,0);wall.AddComponent<BoxCollider2D>().size=new Vector2(.2f,8);
                var camera=new GameObject("Camera").AddComponent<Camera>();camera.tag="MainCamera";camera.orthographic=true;camera.orthographicSize=4;camera.transform.position=new Vector3(0,1,-10);camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.12f,.15f,.2f);
                EditorSceneManager.SaveScene(scene,ScenePath);EditorBuildSettings.scenes=EditorBuildSettings.scenes.Where(s=>s.path!=ScenePath).Concat(new[]{new EditorBuildSettingsScene(ScenePath,true)}).ToArray();AssetDatabase.SaveAssets();
                var report=new SpriteReport{unity_version=Application.unityVersion,metadata_digest=job.metadata_digest,atlas_sha256=job.atlas_sha256,prefab_guid=AssetDatabase.AssetPathToGUID(Folder+"/Robot2D.prefab"),scene_guid=AssetDatabase.AssetPathToGUID(ScenePath),clip_guid=AssetDatabase.AssetPathToGUID(Folder+"/Walk.anim"),clip_seconds=clip.length,loop=clip.isLooping,sprites=sprites.Select(s=>{AssetDatabase.TryGetGUIDAndLocalFileIdentifier(s,out string guid,out long id);return new SpriteBinding{name=s.name,guid=guid,local_id=id,x=s.rect.x,width=s.rect.width,height=s.rect.height,pivot_x=s.pivot.x,pivot_y=s.pivot.y};}).ToArray()};
                File.WriteAllText(PolyForge.Editor.PolyForgeBuilder.Argument("-polyforgeOutput"),JsonUtility.ToJson(report,true));EditorApplication.Exit(0);
            }
            catch(Exception e){Debug.LogException(e);EditorApplication.Exit(5);}
        }
    }
}
