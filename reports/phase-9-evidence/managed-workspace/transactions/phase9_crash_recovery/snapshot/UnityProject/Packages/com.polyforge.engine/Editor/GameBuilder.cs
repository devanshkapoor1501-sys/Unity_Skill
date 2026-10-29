using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using PolyForge.Editor;

namespace PolyForge.Game.Editor
{
    [Serializable] public class GameInput
    {
        public string schema_version;public string input_digest;public string game_contract_digest;public string scene_id;
        public int seed;public ActorSpec player;public ActorSpec[] enemies;public ActorSpec[] static_actors;public string project_name;public string ground_id;
        public string[] obstacle_ids;public float[] half_extents;public float survival_seconds;
        public int health;public float player_speed;public float enemy_speed;public int damage;
        public float fixed_delta_seconds;public float wall_thickness;
        public string wall_fbx;public string wall_material;public string player_output;
    }
    [Serializable] public class GameReport
    {
        public string schema_version="1.0.0";public string status="PASS";public string input_digest;public string game_contract_digest;
        public string unity_version;public string scene_path;public string scene_guid;public string player_id;public int enemy_count;
        public string playmode_status="NOT_RUN";
    }
    public static class GameBuilder
    {
        public const string ScenePath="Assets/PolyForgeGenerated/Game/PlayableArena.unity";
        static Vector3 V(float[] a)=>new Vector3(a[0],a[1],a[2]);
        public static GameInput Read()=>JsonUtility.FromJson<GameInput>(File.ReadAllText(PolyForgeBuilder.Argument("-polyforgeGameInput")));
        public static void BuildBatch()
        {
            try
            {
                var job=Read();Build(job);
                var report=new GameReport{input_digest=job.input_digest,game_contract_digest=job.game_contract_digest,unity_version=Application.unityVersion,
                    scene_path=ScenePath,scene_guid=AssetDatabase.AssetPathToGUID(ScenePath),player_id=job.player.id,enemy_count=job.enemies.Length};
                File.WriteAllText(PolyForgeBuilder.Argument("-polyforgeOutput"),JsonUtility.ToJson(report,true));EditorApplication.Exit(0);
            }
            catch(Exception e){Debug.LogException(e);EditorApplication.Exit(5);}
        }
        static GameObject Instance(string id,string name,Vector3 position)
        {
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(PolyForgeBuilder.PrefabPath(id));
            if(prefab==null)throw new Exception("Missing source prefab "+id);
            var go=(GameObject)PrefabUtility.InstantiatePrefab(prefab);go.name=name;go.transform.position=position;return go;
        }
        static Bounds BoundsOf(GameObject go)
        {
            var all=go.GetComponentsInChildren<MeshRenderer>();var bounds=all[0].bounds;
            foreach(var r in all.Skip(1))bounds.Encapsulate(r.bounds);return bounds;
        }
        public static void Build(GameInput job)
        {
            if(job.schema_version!="1.0.0" || job.survival_seconds!=30 || job.player==null)throw new Exception("Invalid supported arena request");
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var ground=Instance(job.ground_id,"Ground",Vector3.zero);ground.transform.position-=Vector3.up*BoundsOf(ground).size.y;
            for(int i=0;i<job.obstacle_ids.Length;i++)Instance(job.obstacle_ids[i],"Obstacle_"+i,new Vector3(i*2,0,0));
            foreach(var actor in job.static_actors??Array.Empty<ActorSpec>())Instance(actor.asset_id,actor.id,V(actor.spawn_xyz));
            var session=new GameObject("Arena").AddComponent<ArenaSession>();
            session.seed=job.seed;session.sceneId=job.scene_id;session.inputDigest=job.input_digest;session.survivalSeconds=job.survival_seconds;session.playerSpawn=V(job.player.spawn_xyz);
            var playerGo=Instance(job.player.asset_id,job.player.id,session.playerSpawn);
            var size=BoundsOf(playerGo).size;
            foreach(var c in playerGo.GetComponentsInChildren<Collider>())UnityEngine.Object.DestroyImmediate(c);
            var motor=playerGo.AddComponent<CharacterController>();motor.height=size.y;motor.radius=Mathf.Max(size.x,size.z)*.35f;
            motor.center=Vector3.up*size.y/2;motor.stepOffset=Mathf.Min(.25f,size.y*.2f);motor.skinWidth=.03f;
            playerGo.AddComponent<Health>().Configure(job.health,job.health);
            var player=playerGo.AddComponent<PlayerController>();player.session=session;player.speed=job.player_speed;session.player=player;
            session.enemies=job.enemies.Select(a=>
            {
                var go=Instance(a.asset_id,a.id,V(a.spawn_xyz));
                var body=go.AddComponent<Rigidbody>();body.isKinematic=true;body.useGravity=false;body.constraints=RigidbodyConstraints.FreezeRotation;
                var enemy=go.AddComponent<PatrolEnemy>();enemy.session=session;enemy.spawn=V(a.spawn_xyz);enemy.speed=job.enemy_speed;
                enemy.waypoints=new[]{enemy.spawn+new Vector3(2,0,0),enemy.spawn+new Vector3(2,0,2),enemy.spawn+new Vector3(0,0,2),enemy.spawn};
                var bounds=BoundsOf(go);var contact=go.AddComponent<CapsuleCollider>();contact.isTrigger=true;
                contact.center=Vector3.up*bounds.size.y/2;contact.radius=Mathf.Max(bounds.size.x,bounds.size.z)/2+.4f;contact.height=bounds.size.y+.8f;
                var damage=go.AddComponent<ContactDamage>();damage.session=session;damage.amount=job.damage;
                return enemy;
            }).ToArray();
            AssetDatabase.ImportAsset(job.wall_fbx,ImportAssetOptions.ForceSynchronousImport);
            var importer=(ModelImporter)AssetImporter.GetAtPath(job.wall_fbx);importer.globalScale=1;importer.useFileScale=true;importer.materialImportMode=ModelImporterMaterialImportMode.None;importer.importAnimation=false;importer.SaveAndReimport();
            var wallSource=AssetDatabase.LoadAssetAtPath<GameObject>(job.wall_fbx);
            var material=AssetDatabase.LoadAssetAtPath<Material>(job.wall_material);
            for(int i=0;i<4;i++)
            {
                var wall=new GameObject(new[]{"WallNorth","WallSouth","WallEast","WallWest"}[i]);
                var model=(GameObject)PrefabUtility.InstantiatePrefab(wallSource);model.transform.SetParent(wall.transform,false);model.transform.localScale=Vector3.Scale(model.transform.localScale,new Vector3(-1,1,1));
                bool horizontal=i<2;var width=horizontal?job.half_extents[0]*2:job.half_extents[1]*2;
                // Source wall has X length 20; scale only this owned structural instance.
                wall.transform.localScale=new Vector3(width/20,1,1);
                wall.transform.position=horizontal?new Vector3(0,0,(i==0?1:-1)*(job.half_extents[1]-job.wall_thickness/2)):new Vector3((i==2?1:-1)*(job.half_extents[0]-job.wall_thickness/2),0,0);
                if(!horizontal)wall.transform.rotation=Quaternion.Euler(0,90,0);
                foreach(var r in model.GetComponentsInChildren<MeshRenderer>())r.sharedMaterial=material;
                var c=wall.AddComponent<BoxCollider>();c.center=new Vector3(0,.6f,0);c.size=new Vector3(20,1.2f,job.wall_thickness);
            }
            var light=new GameObject("Sun").AddComponent<Light>();light.type=LightType.Directional;light.intensity=2;light.transform.rotation=Quaternion.Euler(50,-30,0);
            var camera=new GameObject("Main Camera").AddComponent<Camera>();camera.tag="MainCamera";camera.orthographic=true;camera.orthographicSize=Mathf.Max(job.half_extents[0],job.half_extents[1])*1.4f;
            camera.transform.position=new Vector3(12,14,-12);camera.transform.LookAt(Vector3.zero);camera.farClipPlane=300;
            new GameObject("HUD").AddComponent<ArenaHud>().session=session;
            session.gameObject.AddComponent<ArenaPerformance>().session=session;
            Time.fixedDeltaTime=job.fixed_delta_seconds;
            Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));EditorSceneManager.SaveScene(scene,ScenePath);
            EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene(ScenePath,true)};
            AssetDatabase.SaveAssets();
        }
        public static void BuildPlayerBatch()
        {
            try
            {
                var job=Read();Directory.CreateDirectory(Path.GetDirectoryName(job.player_output));
                PlayerSettings.productName=string.IsNullOrEmpty(job.project_name)?"PolyForge Arena":job.project_name;PlayerSettings.companyName="PolyForge";
                PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone,ScriptingImplementation.Mono2x);
                PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
                var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},locationPathName=job.player_output,target=BuildTarget.StandaloneWindows64,options=BuildOptions.Development});
                if(report.summary.result!=BuildResult.Succeeded)throw new Exception("Standalone build "+report.summary.result);
                EditorApplication.Exit(0);
            }
            catch(Exception e){Debug.LogException(e);EditorApplication.Exit(5);}
        }
    }
}
