using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace PolyForge.Editor.Tests
{
    public class ForensicsTests
    {
        [TestCase("scale")][TestCase("source")][TestCase("camera")]
        public void SceneOverridesAreDetected(string fault)
        {
            var request = PolyForgeBuilder.ReadRequest();
            try
            {
                var scene = EditorSceneManager.OpenScene(PolyForgeBuilder.Generated + "/Scenes/Arena.unity", OpenSceneMode.Single);
                var binding = scene.GetRootGameObjects().SelectMany(x => x.GetComponentsInChildren<PrefabBinding>()).First();
                if (fault == "scale") binding.transform.localScale = Vector3.one * 100;
                if (fault == "source") binding.sourceModel = AssetDatabase.LoadAssetAtPath<GameObject>(PolyForgeBuilder.PrefabPath(binding.semanticId));
                if (fault == "camera") Object.DestroyImmediate(GameObject.Find("Main Camera").GetComponent<Camera>());
                PrefabUtility.RecordPrefabInstancePropertyModifications(binding);
                PrefabUtility.RecordPrefabInstancePropertyModifications(binding.transform);
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                Assert.That(PolyForgeBuilder.Observe(request).issues.Any(x => x.category.StartsWith("scene")), Is.True, fault);
            }
            finally { PolyForgeBuilder.Build(request); }
        }

        [TestCase("size")][TestCase("center")][TestCase("disabled")][TestCase("meshReference")][TestCase("none")]
        public void ColliderFaultsAreDetected(string fault)
        {
            var original = PolyForgeBuilder.ReadRequest();
            var request = JsonUtility.FromJson<BuildRequest>(JsonUtility.ToJson(original));
            var asset = request.assets[0];
            asset.collider = fault == "meshReference" ? "mesh" : fault == "none" ? "none" : "box";
            try
            {
                PolyForgeBuilder.Build(request);
                var path = PolyForgeBuilder.PrefabPath(asset.id);
                var root = PrefabUtility.LoadPrefabContents(path);
                try
                {
                    if (fault == "size") root.GetComponent<BoxCollider>().size = Vector3.one * 100;
                    if (fault == "center") root.GetComponent<BoxCollider>().center += Vector3.one * 10;
                    if (fault == "disabled") root.GetComponent<BoxCollider>().enabled = false;
                    if (fault == "meshReference") root.GetComponentInChildren<MeshCollider>().sharedMesh = null;
                    if (fault == "none") root.AddComponent<BoxCollider>();
                    PrefabUtility.SaveAsPrefabAsset(root, path);
                }
                finally { PrefabUtility.UnloadPrefabContents(root); }
                Assert.That(PolyForgeBuilder.Observe(request).issues.Any(x => x.category == "collider" && x.asset_id == asset.id), Is.True, fault);
            }
            finally { PolyForgeBuilder.Build(original); }
        }
    }
}
