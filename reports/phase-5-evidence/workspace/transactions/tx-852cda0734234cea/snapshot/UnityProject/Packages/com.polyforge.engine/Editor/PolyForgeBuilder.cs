using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace PolyForge.Editor
{
    [Serializable] public class MaterialSpec { public string id; public float[] base_color_rgba; public float metallic; public float roughness; }
    [Serializable] public class ModuleSpec { public string id; public string name; public string[] material_ids; }
    [Serializable] public class SocketSpec { public string id; public string name; public float[] position_m; }
    [Serializable] public class AssetSpec
    {
        public string id; public string fbx_path; public string sha256; public float[] bounds_m;
        public string collider; public MaterialSpec[] materials; public ModuleSpec[] modules; public SocketSpec[] sockets;
    }
    [Serializable] public class ActorSpec { public string id; public string asset_id; public float[] spawn_xyz; }
    [Serializable] public class BuildRequest
    {
        public string schema_version; public string input_digest; public AssetSpec[] assets; public ActorSpec[] actors;
        public float[] scene_bounds_m;
        public string[] rebuild_asset_ids;
    }
    [Serializable] public class Issue { public string category; public string asset_id; public string expected; public string actual; }
    [Serializable] public class SocketObserved { public string id; public float[] position_m; }
    [Serializable] public class NodeBinding { public string id; public string kind; public string path; public string guid; public long local_id; public string component; }
    [Serializable] public class ColliderObserved { public string kind; public string path; public bool enabled; public bool is_trigger; public float[] center_m; public float[] size_m; public string mesh_guid; public long mesh_local_id; }
    [Serializable] public class SceneInstance { public string scene; public string id; public string asset_id; public string prefab_guid; public string source_guid; public float[] position_m; public float[] scale; public float[] rotation_xyzw; }
    [Serializable] public class Observed
    {
        public string id; public string guid; public string prefab_guid; public string prefab_id;
        public float[] bounds_m; public string[] socket_ids; public SocketObserved[] sockets;
        public string[] material_ids; public int transform_count; public string collider;
        public NodeBinding[] nodes;
        public ColliderObserved[] colliders;
    }
    [Serializable] public class BindingReport
    {
        public string schema_version = "1.0.0"; public string input_digest; public string unity_version;
        public string status; public string verification_scope = "UNITY_EDITOR_STATIC";
        public string gameplay_status = "NOT_RUN"; public Observed[] objects; public Issue[] issues;
        public int scene_object_count; public string[] scene_guids;
        public SceneInstance[] scene_instances; public int camera_count; public int light_count;
    }

    public static class PolyForgeBuilder
    {
        public const string Generated = "Assets/PolyForgeGenerated";
        public static string PrefabPath(string id) => Generated + "/Prefabs/" + id + ".prefab";
        public static string MaterialPath(string id, string material) => Generated + "/Materials/" + id + "/" + material + ".mat";
        public static string Argument(string key)
        {
            var args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, key);
            if (i < 0 || i + 1 >= args.Length) throw new ArgumentException("Missing " + key);
            return args[i + 1];
        }
        public static BuildRequest ReadRequest()
        {
            var request = JsonUtility.FromJson<BuildRequest>(File.ReadAllText(Argument("-polyforgeInput")));
            if (request.schema_version != "1.0.0" || request.assets == null || request.assets.Length == 0)
                throw new ArgumentException("Invalid validated PolyForge request");
            foreach (var a in request.assets)
            {
                if (!System.Text.RegularExpressions.Regex.IsMatch(a.id, @"^[a-zA-Z0-9_-]{1,64}$") ||
                    a.fbx_path != Generated + "/Models/" + a.id + ".fbx")
                    throw new ArgumentException("Asset path is outside generated scope");
            }
            return request;
        }
        public static void BuildBatch() => Batch(true);
        public static void ReconcileBatch() => Batch(false);
        public static void ReimportBatch() => Batch(false, true);
        static void Batch(bool build, bool reimport = false)
        {
            try
            {
                var request = ReadRequest();
                if (reimport) AssetDatabase.ImportAsset(Generated, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ImportRecursive | ImportAssetOptions.ForceSynchronousImport);
                if (build) Build(request);
                var report = Observe(request);
                File.WriteAllText(Argument("-polyforgeOutput"), JsonUtility.ToJson(report, true));
                EditorApplication.Exit(report.issues.Length == 0 ? 0 : 6);
            }
            catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(5); }
        }
        public static void Build(BuildRequest request)
        {
            if (Application.unityVersion != "6000.6.3f1") throw new Exception("Pinned Editor required");
            if (UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline == null)
                throw new Exception("Installed template did not configure URP");
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            foreach (var a in request.assets)
            {
                if (request.rebuild_asset_ids != null && request.rebuild_asset_ids.Length > 0 && !request.rebuild_asset_ids.Contains(a.id)) continue;
                Directory.CreateDirectory(Generated + "/Materials/" + a.id);
                Directory.CreateDirectory(Generated + "/Prefabs");
                AssetDatabase.Refresh();
                var importer = AssetImporter.GetAtPath(a.fbx_path) as ModelImporter;
                if (importer == null) throw new Exception("Missing model " + a.fbx_path);
                // Phase 4 intended settings are verified here against observed geometry.
                importer.globalScale = 1; importer.useFileScale = true; importer.bakeAxisConversion = false;
                importer.importAnimation = false; importer.importCameras = false; importer.importLights = false;
                importer.materialImportMode = ModelImporterMaterialImportMode.None;
                importer.SaveAndReimport();
                var materials = new Dictionary<string, Material>();
                foreach (var spec in a.materials)
                {
                    string path = MaterialPath(a.id, spec.id);
                    var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                    if (m == null)
                    {
                        var shader = Shader.Find("Universal Render Pipeline/Lit");
                        if (shader == null) throw new Exception("URP/Lit is unavailable");
                        m = new Material(shader); AssetDatabase.CreateAsset(m, path);
                    }
                    var c = spec.base_color_rgba;
                    m.SetColor("_BaseColor", new Color(c[0], c[1], c[2], c[3]));
                    m.SetFloat("_Metallic", spec.metallic); m.SetFloat("_Smoothness", 1 - spec.roughness);
                    EditorUtility.SetDirty(m); materials.Add(spec.id, m);
                }
                var root = new GameObject(a.id);
                try
                {
                    var model = AssetDatabase.LoadAssetAtPath<GameObject>(a.fbx_path);
                    var child = (GameObject)PrefabUtility.InstantiatePrefab(model);
                    child.transform.SetParent(root.transform, false);
                    // Blender is right-handed. Unity's FBX conversion reverses X
                    // relative to our semantic coordinates. Correct that basis at
                    // this explicit boundary; the semantic/collider root stays unit.
                    child.transform.localScale = Vector3.Scale(child.transform.localScale, new Vector3(-1, 1, 1));
                    var transforms = child.GetComponentsInChildren<Transform>(true);
                    foreach (var module in a.modules)
                    {
                        var node = transforms.SingleOrDefault(x => x.name == module.name);
                        if (node == null) throw new Exception("Missing exact module " + module.name);
                        var renderer = node.GetComponent<MeshRenderer>();
                        if (renderer == null) throw new Exception("Missing module renderer " + module.name);
                        renderer.sharedMaterials = module.material_ids.Select(x => materials[x]).ToArray();
                    }
                    var binding = root.AddComponent<PrefabBinding>(); binding.semanticId = a.id; binding.sourceModel = model;
                    var bounds = BoundsOf(root);
                    if (a.collider == "box")
                    {
                        var c = root.AddComponent<BoxCollider>(); c.center = bounds.center; c.size = bounds.size;
                    }
                    else if (a.collider == "capsule")
                    {
                        var c = root.AddComponent<CapsuleCollider>(); c.center = bounds.center;
                        c.radius = Mathf.Max(bounds.size.x, bounds.size.z) / 2; c.height = Mathf.Max(bounds.size.y, c.radius * 2); c.direction = 1;
                    }
                    else if (a.collider == "mesh")
                        foreach (var mesh in child.GetComponentsInChildren<MeshFilter>()) mesh.gameObject.AddComponent<MeshCollider>().sharedMesh = mesh.sharedMesh;
                    else if (a.collider != "none") throw new Exception("Unsupported collider");
                    PrefabUtility.SaveAsPrefabAsset(root, PrefabPath(a.id));
                }
                finally { UnityEngine.Object.DestroyImmediate(root); }
            }
            AssetDatabase.SaveAssets();
            BuildScene(request, "Arena", false); BuildScene(request, "Training", true);
            AssetDatabase.SaveAssets();
        }
        static void BuildScene(BuildRequest request, string name, bool training)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = new GameObject("PolyForgeScene");
            for (int i = 0; i < request.assets.Length; i++)
            {
                var a = request.assets[i];
                var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath(a.id)), scene);
                go.name = "asset:" + a.id; go.transform.SetParent(root.transform, false);
                bool ground = a.bounds_m[0] >= request.scene_bounds_m[0] * 0.5f && a.bounds_m[2] >= request.scene_bounds_m[2] * 0.5f;
                go.transform.position = ground ? new Vector3(0, -a.bounds_m[1], 0) : new Vector3(training ? -i * 2 : i * 2, 0, 0);
            }
            foreach (var actor in request.actors)
            {
                var go = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath(actor.asset_id)), scene);
                go.name = "actor:" + actor.id; go.transform.SetParent(root.transform, false);
                go.transform.position = V(actor.spawn_xyz);
            }
            var light = new GameObject("Sun").AddComponent<Light>(); light.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50, -30, 0); light.intensity = 2;
            var camera = new GameObject("Main Camera").AddComponent<Camera>(); camera.tag = "MainCamera";
            camera.transform.position = new Vector3(12, 14, -12); camera.transform.LookAt(Vector3.zero);
            camera.orthographic = true; camera.orthographicSize = Mathf.Max(request.scene_bounds_m[0], request.scene_bounds_m[2]) * 0.7f;
            camera.farClipPlane = 200;
            Directory.CreateDirectory(Generated + "/Scenes");
            EditorSceneManager.SaveScene(scene, Generated + "/Scenes/" + name + ".unity");
        }
        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);
        static float[] A(Vector3 a) => new [] {a.x, a.y, a.z};
        static bool Near(Vector3 a, Vector3 b) => Enumerable.Range(0, 3).All(i => Math.Abs(a[i]-b[i]) <= Math.Max(.002, Math.Abs(b[i])*.02));
        static bool SameCollider(Collider a, Collider b)
        {
            if(a.GetType()!=b.GetType() || a.enabled!=b.enabled || a.isTrigger!=b.isTrigger) return false;
            if(a is BoxCollider x && b is BoxCollider y) return Near(x.center,y.center)&&Near(x.size,y.size);
            if(a is CapsuleCollider c && b is CapsuleCollider d) return Near(c.center,d.center)&&Math.Abs(c.height-d.height)<.002&&Math.Abs(c.radius-d.radius)<.002&&c.direction==d.direction;
            if(a is MeshCollider m && b is MeshCollider n) return m.sharedMesh==n.sharedMesh && m.convex==n.convex;
            return false;
        }
        static Bounds BoundsOf(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<MeshRenderer>(true);
            if (renderers.Length == 0) throw new Exception("No imported geometry");
            var bounds = renderers[0].bounds;
            foreach (var r in renderers.Skip(1)) bounds.Encapsulate(r.bounds);
            return bounds;
        }
        public static BindingReport Observe(BuildRequest request)
        {
            var issues = new List<Issue>(); var objects = new List<Observed>(); bool missingPrefab = false;
            void Fail(string category, string id, object expected, object actual) => issues.Add(new Issue {
                category = category, asset_id = id, expected = expected.ToString(), actual = actual == null ? "null" : actual.ToString() });
            foreach (var a in request.assets)
            {
                var guid = AssetDatabase.AssetPathToGUID(a.fbx_path);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath(a.id));
                if (prefab == null || string.IsNullOrEmpty(guid)) { Fail("binding", a.id, "model and prefab GUID", guid); missingPrefab = true; continue; }
                var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                try
                {
                    var bounds = BoundsOf(instance); var actual = A(bounds.size);
                    for (int i = 0; i < 3; i++) if (Math.Abs(actual[i] - a.bounds_m[i]) > Math.Max(.001, a.bounds_m[i] * .02)) Fail("scale", a.id, a.bounds_m[i], actual[i]);
                    if (Math.Abs(bounds.min.y) > .001 || Math.Abs(bounds.center.x) > .001 || Math.Abs(bounds.center.z) > .001) Fail("pivot", a.id, "base center", bounds.center);
                    var transforms = instance.GetComponentsInChildren<Transform>(true);
                    var sockets = new List<SocketObserved>();
                    var nodes = new List<NodeBinding>();
                    void Bind(Transform t, string id, string kind, string component)
                    {
                        var source = PrefabUtility.GetCorrespondingObjectFromSource(t);
                        AssetDatabase.TryGetGUIDAndLocalFileIdentifier(source, out string nodeGuid, out long localId);
                        if (string.IsNullOrEmpty(nodeGuid) || localId == 0) Fail("binding", a.id, id, "missing local file ID");
                        nodes.Add(new NodeBinding {id=id, kind=kind, path=AnimationUtility.CalculateTransformPath(t, instance.transform), guid=nodeGuid, local_id=localId, component=component});
                    }
                    foreach (var socket in a.sockets)
                    {
                        var found = transforms.Where(x => x.name == socket.name).ToArray();
                        if (found.Length != 1) { Fail("socket", a.id, socket.name, found.Length); continue; }
                        var p = instance.transform.InverseTransformPoint(found[0].position);
                        if (Vector3.Distance(p, V(socket.position_m)) > .002f) Fail("axis", a.id, V(socket.position_m), p);
                        sockets.Add(new SocketObserved {id = socket.id, position_m = A(p)});
                        Bind(found[0], socket.id, "socket", "Transform");
                    }
                    foreach (var m in a.modules)
                    {
                        var t = transforms.SingleOrDefault(x => x.name == m.name);
                        var r = t == null ? null : t.GetComponent<MeshRenderer>();
                        if (r == null) { Fail("binding", a.id, m.name, "missing renderer"); continue; }
                        var expected = m.material_ids.Select(x => AssetDatabase.LoadAssetAtPath<Material>(MaterialPath(a.id, x))).ToArray();
                        if (expected.Any(x => x == null) || !r.sharedMaterials.SequenceEqual(expected)) Fail("material", a.id, m.name, "lost material reference");
                        Bind(t, m.id, "module", "MeshRenderer");
                    }
                    foreach (var spec in a.materials)
                    {
                        var m = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath(a.id, spec.id));
                        if (m == null || m.shader == null || m.shader.name != "Universal Render Pipeline/Lit") { Fail("material", a.id, spec.id, "missing URP material"); continue; }
                        var color = m.GetColor("_BaseColor");
                        if (Enumerable.Range(0,4).Any(i => Math.Abs(color[i] - spec.base_color_rgba[i]) > .0001f) ||
                            Math.Abs(m.GetFloat("_Metallic") - spec.metallic) > .0001f ||
                            Math.Abs(m.GetFloat("_Smoothness") - (1-spec.roughness)) > .0001f)
                            Fail("material", a.id, spec.id, "changed material parameters");
                    }
                    var binding = instance.GetComponent<PrefabBinding>();
                    if (binding == null || binding.semanticId != a.id || binding.sourceModel != AssetDatabase.LoadAssetAtPath<GameObject>(a.fbx_path)) Fail("component", a.id, "PrefabBinding with source reference", "missing/mismatched");
                    var colliders = instance.GetComponentsInChildren<Collider>(true);
                    var details = new List<ColliderObserved>();
                    var expectedCenter = new Vector3(0, a.bounds_m[1]/2, 0);
                    string observedKind = colliders.Length == 0 ? "none" : colliders.All(x => x is MeshCollider) ? "mesh" : colliders.Length == 1 && colliders[0] is BoxCollider ? "box" : colliders.Length == 1 && colliders[0] is CapsuleCollider ? "capsule" : "mixed";
                    if (observedKind != a.collider) Fail("collider", a.id, a.collider, observedKind);
                    foreach (var collider in colliders)
                    {
                        var detail = new ColliderObserved {kind=collider.GetType().Name, path=AnimationUtility.CalculateTransformPath(collider.transform, instance.transform), enabled=collider.enabled, is_trigger=collider.isTrigger};
                        if (!collider.enabled || collider.isTrigger) Fail("collider", a.id, "enabled solid collider", "disabled/trigger");
                        if (collider is BoxCollider box)
                        {
                            detail.center_m=A(box.center); detail.size_m=A(box.size);
                            if (box.gameObject != instance || !Near(box.center, expectedCenter) || !Near(box.size, V(a.bounds_m))) Fail("collider", a.id, "box matches semantic geometry", box.size + " at " + box.center);
                        }
                        else if (collider is CapsuleCollider capsule)
                        {
                            var radius=Mathf.Max(a.bounds_m[0],a.bounds_m[2])/2; var height=Mathf.Max(a.bounds_m[1],radius*2);
                            detail.center_m=A(capsule.center); detail.size_m=new[]{capsule.radius*2,capsule.height,capsule.radius*2};
                            if (capsule.gameObject != instance || capsule.direction != 1 || !Near(capsule.center,expectedCenter) || Math.Abs(capsule.radius-radius)>.002 || Math.Abs(capsule.height-height)>.002) Fail("collider",a.id,"fitted Y capsule","incorrect capsule geometry");
                        }
                        else if (collider is MeshCollider mesh)
                        {
                            var filter=mesh.GetComponent<MeshFilter>();
                            if (mesh.sharedMesh == null || filter == null || mesh.sharedMesh != filter.sharedMesh) Fail("collider",a.id,"matching mesh reference","missing/wrong mesh");
                            else AssetDatabase.TryGetGUIDAndLocalFileIdentifier(mesh.sharedMesh,out detail.mesh_guid,out detail.mesh_local_id);
                        }
                        details.Add(detail);
                    }
                    if (a.collider == "mesh" && colliders.Length != instance.GetComponentsInChildren<MeshFilter>(true).Length) Fail("collider",a.id,"one collider per mesh","incomplete mesh coverage");
                    objects.Add(new Observed {id=a.id, guid=guid, prefab_guid=AssetDatabase.AssetPathToGUID(PrefabPath(a.id)), prefab_id=PrefabPath(a.id), bounds_m=actual,
                        socket_ids=sockets.Select(x=>x.id).ToArray(), sockets=sockets.ToArray(), nodes=nodes.ToArray(), colliders=details.ToArray(), material_ids=a.materials.Select(x=>x.id).ToArray(), transform_count=transforms.Length, collider=observedKind});
                }
                finally { UnityEngine.Object.DestroyImmediate(instance); }
            }
            int count = 0; int cameraCount=0; int lightCount=0; var sceneGuids = new List<string>(); var sceneInstances=new List<SceneInstance>();
            foreach (var name in new [] {"Arena", "Training"})
            {
                string path = Generated + "/Scenes/" + name + ".unity";
                if (missingPrefab) { Fail("scene", name, "complete prefab graph", "not opened: missing prefab"); continue; }
                if (AssetDatabase.LoadAssetAtPath<SceneAsset>(path) == null) { Fail("scene", name, "scene", "missing"); continue; }
                var scene = EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
                count += scene.GetRootGameObjects().Sum(x=>x.GetComponentsInChildren<Transform>(true).Length);
                var instances = scene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<PrefabBinding>(true)).ToArray();
                if (instances.Length != request.assets.Length + request.actors.Length) Fail("scene", name, request.assets.Length + request.actors.Length, instances.Length);
                var wanted=new Dictionary<string,(string asset,Vector3 position)>();
                for(int i=0;i<request.assets.Length;i++)
                {
                    var a=request.assets[i]; bool ground=a.bounds_m[0]>=request.scene_bounds_m[0]*.5f && a.bounds_m[2]>=request.scene_bounds_m[2]*.5f;
                    wanted.Add("asset:"+a.id,(a.id,ground?new Vector3(0,-a.bounds_m[1],0):new Vector3(name=="Training"?-i*2:i*2,0,0)));
                }
                foreach(var actor in request.actors) wanted.Add("actor:"+actor.id,(actor.asset_id,V(actor.spawn_xyz)));
                foreach(var entry in wanted)
                {
                    var matches=instances.Where(x=>x.gameObject.name==entry.Key).ToArray();
                    if(matches.Length!=1){Fail("scene_instance",entry.Value.asset,"one named semantic instance " + entry.Key,matches.Length);continue;}
                    var binding=matches[0]; var go=binding.gameObject; var asset=entry.Value.asset;
                    var prefabPath=PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(go);
                    var source=AssetDatabase.LoadAssetAtPath<GameObject>(request.assets.Single(x=>x.id==asset).fbx_path);
                    var q=go.transform.rotation;
                    sceneInstances.Add(new SceneInstance {scene=name,id=go.name,asset_id=binding.semanticId,prefab_guid=AssetDatabase.AssetPathToGUID(prefabPath),source_guid=binding.sourceModel==null?"":AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(binding.sourceModel)),position_m=A(go.transform.position),scale=A(go.transform.lossyScale),rotation_xyzw=new[]{q.x,q.y,q.z,q.w}});
                    if(binding.semanticId!=asset || binding.sourceModel!=source || prefabPath!=PrefabPath(asset)) Fail("scene_instance",asset,"matching prefab/source/semantic identity",entry.Key+": incorrect scene reference");
                    if(!Near(go.transform.position,entry.Value.position) || !Near(go.transform.lossyScale,Vector3.one) || Quaternion.Angle(go.transform.rotation,Quaternion.identity)>.01f) Fail("scene_instance",asset,"declared spawn, unit scale and identity rotation",entry.Key+": scene transform override");
                    var expectedPrefab=AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath(asset));
                    var actualColliders=go.GetComponentsInChildren<Collider>(true); var wantedColliders=expectedPrefab.GetComponentsInChildren<Collider>(true);
                    if(actualColliders.Length!=wantedColliders.Length || actualColliders.Where((x,i)=>!SameCollider(x,wantedColliders[i])).Any()) Fail("scene_instance",asset,"matching collider bindings",entry.Key+": scene collider override");
                    foreach(var module in request.assets.Single(x=>x.id==asset).modules)
                    {
                        var renderer=go.GetComponentsInChildren<MeshRenderer>(true).SingleOrDefault(x=>x.name==module.name);
                        if(renderer==null || !renderer.sharedMaterials.SequenceEqual(module.material_ids.Select(x=>AssetDatabase.LoadAssetAtPath<Material>(MaterialPath(asset,x))))) Fail("scene_instance",asset,"matching material bindings",entry.Key+": scene material override");
                    }
                }
                var cameras=scene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<Camera>(true)).ToArray(); cameraCount+=cameras.Length;
                if(cameras.Length!=1 || !cameras[0].enabled || cameras[0].tag!="MainCamera" || !cameras[0].orthographic) Fail("scene_camera",name,"one enabled tagged orthographic camera",cameras.Length);
                var lights=scene.GetRootGameObjects().SelectMany(x=>x.GetComponentsInChildren<Light>(true)).ToArray(); lightCount+=lights.Length;
                if(lights.Length!=1 || !lights[0].enabled || lights[0].type!=LightType.Directional) Fail("scene_light",name,"one enabled directional light",lights.Length);
                sceneGuids.Add(AssetDatabase.AssetPathToGUID(path));
            }
            return new BindingReport { input_digest=request.input_digest, unity_version=Application.unityVersion,
                status=issues.Count == 0 ? "PASS" : "FAIL", objects=objects.ToArray(), issues=issues.ToArray(), scene_object_count=count, scene_guids=sceneGuids.ToArray(),scene_instances=sceneInstances.ToArray(),camera_count=cameraCount,light_count=lightCount };
        }
    }
}
