using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class ModelingImportProbe
{
    [Serializable] private class Input { public Model[] models; }
    [Serializable] private class Model
    {
        public string path;
        public float[] lo, hi;
        public int meshCount;
        public Socket[] sockets;
    }
    [Serializable] private class Socket { public string id; public float[] position; }

    private static Vector3 Vector(float[] value) => new Vector3(value[0], value[1], value[2]);

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }

    public static void Run()
    {
        var args = Environment.GetCommandLineArgs();
        var input = JsonUtility.FromJson<Input>(File.ReadAllText(args[Array.IndexOf(args, "-modelingInput") + 1]));
        Check(Application.unityVersion == "6000.6.3f1", "Wrong Editor version");
        foreach (var model in input.models)
        {
            var options = ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate;
            AssetDatabase.ImportAsset(model.path, options);
            var importer = (ModelImporter)AssetImporter.GetAtPath(model.path);
            importer.preserveHierarchy = true;
            importer.SaveAndReimport();
            var guid = AssetDatabase.AssetPathToGUID(model.path);
            Check(guid.Length == 32, $"Missing import GUID for {model.path}");
            AssetDatabase.ImportAsset(model.path, options);
            Check(AssetDatabase.AssetPathToGUID(model.path) == guid, $"Unstable GUID for {model.path}");
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(model.path);
            Check(prefab != null, $"Missing imported model {model.path}");
            var filters = prefab.GetComponentsInChildren<MeshFilter>(true);
            Check(filters.Length == model.meshCount, $"Wrong mesh inventory for {model.path}");
            var min = Vector3.one * float.PositiveInfinity;
            var max = Vector3.one * float.NegativeInfinity;
            foreach (var filter in filters)
            {
                var mesh = filter.sharedMesh;
                Check(mesh != null && mesh.vertexCount > 0 && mesh.uv.Length == mesh.vertexCount,
                      $"Missing geometry or UVs for {filter.name}");
                foreach (var vertex in mesh.vertices)
                {
                    var point = filter.transform.TransformPoint(vertex);
                    min = Vector3.Min(min, point);
                    max = Vector3.Max(max, point);
                }
            }
            Check(Vector3.Distance(min, Vector(model.lo)) < 0.005f &&
                  Vector3.Distance(max, Vector(model.hi)) < 0.005f,
                  $"Bounds for {model.path}: observed {min} to {max}, expected {Vector(model.lo)} to {Vector(model.hi)}");
            foreach (var socket in model.sockets)
            {
                var matches = prefab.GetComponentsInChildren<Transform>(true)
                    .Where(t => t.name.EndsWith(":socket:" + socket.id, StringComparison.Ordinal)).ToArray();
                Check(matches.Length == 1, $"Socket inventory differs for {model.path}: {socket.id}");
                Check(Vector3.Distance(matches[0].position, Vector(socket.position)) < 0.005f,
                      $"Socket {socket.id} moved in {model.path}: {matches[0].position}");
            }
            Debug.Log($"PolyForge modeling import passed {model.path} {guid} {min} {max}");
        }
        File.WriteAllText(args[Array.IndexOf(args, "-modelingResult") + 1], $"{{\"models\":{input.models.Length}}}");
    }
}
