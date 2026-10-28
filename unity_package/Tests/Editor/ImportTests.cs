using System.Linq;
using System.IO;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace PolyForge.Editor.Tests
{
    public class ImportTests
    {
        [Test] public void ChangedMaterialValueIsDetected()
        {
            var request = PolyForgeBuilder.ReadRequest(); var a = request.assets[0];
            var material = AssetDatabase.LoadAssetAtPath<Material>(PolyForgeBuilder.MaterialPath(a.id, a.materials[0].id));
            try
            {
                material.SetFloat("_Metallic", a.materials[0].metallic < .5f ? 1 : 0);
                Assert.That(PolyForgeBuilder.Observe(request).issues.Any(x => x.category == "material" && x.asset_id == a.id), Is.True);
            }
            finally { PolyForgeBuilder.Build(request); }
        }

        [Test] public void MissingPrefabGuidIsDetectedAndNativeBytesRestoreIt()
        {
            var request = PolyForgeBuilder.ReadRequest(); var a = request.assets[0];
            var path = PolyForgeBuilder.PrefabPath(a.id); var bytes = File.ReadAllBytes(path); var meta = File.ReadAllBytes(path + ".meta");
            var guid = AssetDatabase.AssetPathToGUID(path);
            try
            {
                AssetDatabase.DeleteAsset(path);
                Assert.That(PolyForgeBuilder.Observe(request).issues.Any(x => x.category == "binding" && x.asset_id == a.id), Is.True);
            }
            finally
            {
                File.WriteAllBytes(path, bytes); File.WriteAllBytes(path + ".meta", meta);
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                PolyForgeBuilder.Build(request);
            }
            Assert.That(AssetDatabase.AssetPathToGUID(path), Is.EqualTo(guid));
            Assert.That(PolyForgeBuilder.Observe(request).issues, Is.Empty);
        }
        [Test] public void ImportedDimensionsSocketsAndBindingsMatchIndependentSource()
        {
            var request = PolyForgeBuilder.ReadRequest();
            var report = PolyForgeBuilder.Observe(request);
            Assert.That(report.issues, Is.Empty, string.Join("\n", report.issues.Select(x => x.category + ":" + x.asset_id)));
            Assert.That(report.objects.Length, Is.EqualTo(request.assets.Length));
            foreach (var asset in request.assets)
            {
                var observed = report.objects.Single(x => x.id == asset.id);
                Assert.That(observed.guid.Length, Is.EqualTo(32));
                Assert.That(observed.prefab_guid.Length, Is.EqualTo(32));
                for (int i = 0; i < 3; i++) Assert.That(observed.bounds_m[i], Is.EqualTo(asset.bounds_m[i]).Within(System.Math.Max(0.001, asset.bounds_m[i] * 0.02)));
                Assert.That(observed.socket_ids, Is.EquivalentTo(asset.sockets.Select(x => x.id)));
            }
        }

        [Test] public void NativeMaterialParametersMatchLinearSidecars()
        {
            foreach (var a in PolyForgeBuilder.ReadRequest().assets)
            foreach (var expected in a.materials)
            {
                var m = AssetDatabase.LoadAssetAtPath<Material>(PolyForgeBuilder.MaterialPath(a.id, expected.id));
                Assert.That(m, Is.Not.Null);
                Assert.That(m.shader.name, Is.EqualTo("Universal Render Pipeline/Lit"));
                var color = m.GetColor("_BaseColor");
                for (int i = 0; i < 4; i++) Assert.That(color[i], Is.EqualTo(expected.base_color_rgba[i]).Within(0.0001f));
                Assert.That(m.GetFloat("_Metallic"), Is.EqualTo(expected.metallic).Within(0.0001f));
                Assert.That(m.GetFloat("_Smoothness"), Is.EqualTo(1 - expected.roughness).Within(0.0001f));
            }
        }

        [Test] public void RepeatedNativeBuildPreservesGuidsHierarchyAndSceneInstances()
        {
            var request = PolyForgeBuilder.ReadRequest();
            var before = PolyForgeBuilder.Observe(request);
            PolyForgeBuilder.Build(request);
            var after = PolyForgeBuilder.Observe(request);
            Assert.That(after.issues, Is.Empty);
            Assert.That(after.scene_object_count, Is.EqualTo(before.scene_object_count));
            Assert.That(after.objects.Select(x => x.guid), Is.EqualTo(before.objects.Select(x => x.guid)));
            Assert.That(after.objects.Select(x => x.prefab_guid), Is.EqualTo(before.objects.Select(x => x.prefab_guid)));
            Assert.That(after.objects.Select(x => x.transform_count), Is.EqualTo(before.objects.Select(x => x.transform_count)));
            Assert.That(after.objects.SelectMany(x => x.nodes).Select(x => x.guid + ":" + x.local_id + ":" + x.path),
                        Is.EqualTo(before.objects.SelectMany(x => x.nodes).Select(x => x.guid + ":" + x.local_id + ":" + x.path)));
        }

        [TestCase("scale")][TestCase("material")][TestCase("socket")][TestCase("component")]
        public void IndependentFaultsAreDetected(string fault)
        {
            var request = PolyForgeBuilder.ReadRequest();
            var expected = JsonUtility.FromJson<BuildRequest>(JsonUtility.ToJson(request));
            var a = expected.assets.FirstOrDefault(x => x.sockets.Length > 0) ?? expected.assets[0];
            var path = PolyForgeBuilder.PrefabPath(a.id);
            var root = PrefabUtility.LoadPrefabContents(path);
            try
            {
                if (fault == "scale") root.transform.localScale *= 100;
                if (fault == "material") root.GetComponentInChildren<MeshRenderer>().sharedMaterial = null;
                if (fault == "socket")
                {
                    if (a.sockets.Length > 0) root.GetComponentsInChildren<Transform>().First(x => x.name == a.sockets[0].name).name = "renamed_socket";
                    else a.sockets = new [] { new SocketSpec {id="missing_test_socket",name="__absent_fault_fixture_socket__",position_m=new float[3]} };
                }
                if (fault == "component") Object.DestroyImmediate(root.GetComponent<PrefabBinding>());
                PrefabUtility.SaveAsPrefabAsset(root, path);
                var report = PolyForgeBuilder.Observe(expected);
                Assert.That(report.issues.Any(x => x.asset_id == a.id && x.category == fault), Is.True, fault);
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(root);
                PolyForgeBuilder.Build(request);
            }
            Assert.That(PolyForgeBuilder.Observe(request).issues, Is.Empty);
        }
    }
}
