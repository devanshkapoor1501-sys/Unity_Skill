using System.Linq;
using System;
using System.IO;
using System.Collections.Generic;
using Object = UnityEngine.Object;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace PolyForge.Editor.Tests
{
    public class ForensicsTests
    {
        [Test] public void UndeclaredTextureBindingsAreDetected()
        {
            var original=PolyForgeBuilder.ReadRequest();
            var request=JsonUtility.FromJson<BuildRequest>(JsonUtility.ToJson(original));
            var asset=request.assets[0];var spec=asset.materials[0];spec.textures=Array.Empty<TextureSpec>();
            // Observe opens native scenes; keep the transient fault alive across their unloads.
            var image=new Texture2D(2,2){hideFlags=HideFlags.HideAndDontSave};
            try
            {
                PolyForgeBuilder.Build(request);
                var m=AssetDatabase.LoadAssetAtPath<Material>(PolyForgeBuilder.MaterialPath(asset.id,spec.id));
                Assert.That(PolyForgeBuilder.Observe(request).issues,Is.Empty);
                Assert.That(image != null,Is.True,"Injected texture survives native scene setup");
                Assert.That(m == AssetDatabase.LoadAssetAtPath<Material>(PolyForgeBuilder.MaterialPath(asset.id,spec.id)),Is.True,"Fault targets the currently loaded material");
                foreach(var role in new[]{"base_color","normal","normalKeyword"})
                {
                    m.SetTexture("_BaseMap",null);m.SetTexture("_BumpMap",null);m.DisableKeyword("_NORMALMAP");
                    if(role=="normalKeyword")m.EnableKeyword("_NORMALMAP");
                    else m.SetTexture(role=="normal"?"_BumpMap":"_BaseMap",image);
                    var report=PolyForgeBuilder.Observe(request);
                    Assert.That(report.issues.Any(x=>x.category=="texture"&&x.asset_id==asset.id),Is.True,role);
                    if(role!="normalKeyword")
                    {
                        var observed=report.objects.Single(x=>x.id==asset.id).textures.Single(x=>x.material_id==spec.id&&x.kind==role);
                        Assert.That(observed.has_texture,Is.True,"Actual in-memory Texture2D reference");
                        Assert.That(observed.material_texture_path,Is.Empty,"Transient texture has no asset path");
                    }
                }
            }
            finally {Object.DestroyImmediate(image);PolyForgeBuilder.Build(original);}
        }

        [TestCase("srgb")][TestCase("normalType")][TestCase("normalKeyword")][TestCase("reference")][TestCase("bytes")]
        public void SuppliedTextureFaultsAreDetected(string fault)
        {
            var original=PolyForgeBuilder.ReadRequest();
            var request=JsonUtility.FromJson<BuildRequest>(JsonUtility.ToJson(original));
            var asset=request.assets[0];var material=asset.materials[0];
            var bytes=Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEUlEQVR4nGNoaPj/H4QZYAwAZ9IL+XOQc0UAAAAASUVORK5CYII=");
            string digest;
            using(var sha=System.Security.Cryptography.SHA256.Create())digest=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
            var saved=new Dictionary<string,byte[]>();
            material.textures=new[]{"base_color","normal"}.Select(role=>new TextureSpec{kind=role,color_space=role=="normal"?"linear":"srgb",
                path=PolyForgeBuilder.Generated+"/Textures/"+asset.id+"/"+material.id+"/"+role+".png",sha256=digest,source_path="native-test-fixture.png"}).ToArray();
            foreach(var texture in material.textures)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(texture.path));
                foreach(var path in new[]{texture.path,texture.path+".meta"})saved[path]=File.Exists(path)?File.ReadAllBytes(path):null;
                File.WriteAllBytes(texture.path,bytes);
            }
            try
            {
                PolyForgeBuilder.Build(request);
                var report=PolyForgeBuilder.Observe(request);Assert.That(report.issues,Is.Empty);
                var imported=report.objects.Single(a=>a.id==asset.id).textures;
                Assert.That(imported.Length,Is.EqualTo(2));
                Assert.That(imported.Single(t=>t.kind=="base_color").srgb,Is.True);
                Assert.That(imported.Single(t=>t.kind=="normal").texture_type,Is.EqualTo("NormalMap"));
                var color=material.textures[0];var normal=material.textures[1];
                var m=AssetDatabase.LoadAssetAtPath<Material>(PolyForgeBuilder.MaterialPath(asset.id,material.id));
                if(fault=="srgb"){var ti=(TextureImporter)AssetImporter.GetAtPath(color.path);ti.sRGBTexture=false;ti.SaveAndReimport();}
                if(fault=="normalType"){var ti=(TextureImporter)AssetImporter.GetAtPath(normal.path);ti.textureType=TextureImporterType.Default;ti.SaveAndReimport();}
                if(fault=="normalKeyword")m.DisableKeyword("_NORMALMAP");
                if(fault=="reference")m.SetTexture("_BaseMap",null);
                if(fault=="bytes")File.WriteAllBytes(color.path,new byte[]{1,2,3});
                Assert.That(PolyForgeBuilder.Observe(request).issues.Any(x=>x.category=="texture"&&x.asset_id==asset.id),Is.True,fault);
            }
            finally
            {
                foreach(var pair in saved)
                {
                    if(pair.Value==null){if(File.Exists(pair.Key))File.Delete(pair.Key);}
                    else File.WriteAllBytes(pair.Key,pair.Value);
                }
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                PolyForgeBuilder.Build(original);
            }
        }

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
