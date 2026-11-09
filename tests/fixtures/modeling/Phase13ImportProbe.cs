using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

// Only verifier-owned expectations enter this probe. All imported assets are copies.
public static class Phase13ImportProbe
{
    [Serializable] private class Input { public Model[] models; }
    [Serializable] private class Model
    {
        public string attemptId, kind, path, sha256;
        public float coordinateTolerance, boundsTolerance;
        public float[] boundsMin, boundsMax;
        public string[] materials;
        public Socket[] sockets;
        public Module[] modules;
    }
    [Serializable] private class Socket { public string id; public float[] position; }
    [Serializable] private class Module
    {
        public string id, material;
        public float[] boundsMin, boundsMax;
    }
    [Serializable] private class Receipt
    {
        public string unityVersion, fatal;
        public List<Observation> observations = new List<Observation>();
    }
    [Serializable] private class Observation
    {
        public string attemptId, kind, path, sha256, guid, guidAfterReimport;
        public string metaSha256, metaSha256AfterReimport;
        public string[] expectedMaterials, materials;
        public float[] expectedMin, expectedMax, observedMin, observedMax;
        public bool passed, preserveHierarchy, bakeAxisConversion, useFileScale;
        public float globalScale, fileScale;
        public double elapsedSeconds;
        public int meshCount, vertexCount, uvCount, triangleCount, degenerateTriangles;
        public List<string> failures = new List<string>();
        public List<SocketObservation> sockets = new List<SocketObservation>();
        public List<ModuleObservation> modules = new List<ModuleObservation>();
        public List<Negative> negatives = new List<Negative>();
    }
    [Serializable] private class SocketObservation
    {
        public string id;
        public int count;
        public float[] expected, observed;
        public float distance;
        public bool passed;
    }
    [Serializable] private class ModuleObservation
    {
        public string id, expectedMaterial;
        public int count;
        public string[] materials;
        public float[] expectedMin, expectedMax, observedMin, observedMax;
        public bool passed;
    }
    [Serializable] private class Negative
    {
        public string id, socketId;
        public bool applicable, detected, cleanedUp;
        public float[] observed;
    }

    private static Vector3 Vector(float[] p) => new Vector3(p[0], p[1], p[2]);
    private static float[] Values(Vector3 p) => new[] { p.x, p.y, p.z };
    private static bool Finite(float n) => !float.IsNaN(n) && !float.IsInfinity(n);
    private static bool Finite(Vector3 p) => Finite(p.x) && Finite(p.y) && Finite(p.z);
    private static string Sha256(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    private static void Check(Observation row, bool condition, string failure)
    {
        if (!condition)
            row.failures.Add(failure);
    }

    private static Transform[] Sockets(GameObject root, string id) =>
        root.GetComponentsInChildren<Transform>(true)
            .Where(t => t.name.EndsWith(":socket:" + id, StringComparison.Ordinal)).ToArray();

    private static SocketObservation SocketPosition(GameObject root, Socket socket, float tolerance)
    {
        var matches = Sockets(root, socket.id);
        var row = new SocketObservation { id = socket.id, expected = socket.position, count = matches.Length };
        if (matches.Length == 1 && Finite(matches[0].position))
        {
            row.observed = Values(matches[0].position);
            row.distance = Vector3.Distance(matches[0].position, Vector(socket.position));
            row.passed = row.distance <= tolerance;
        }
        return row;
    }

    private static string[] MaterialNames(MeshRenderer renderer) => renderer == null
        ? Array.Empty<string>()
        : renderer.sharedMaterials.Select(m => m == null ? "<null>" : m.name).ToArray();

    private static void AddBounds(IEnumerable<Vector3> points, ref Vector3 min, ref Vector3 max)
    {
        foreach (var point in points)
        {
            min = Vector3.Min(min, point);
            max = Vector3.Max(max, point);
        }
    }

    private static bool Near(Vector3 point, float[] expectation, float tolerance)
    {
        if (expectation == null || expectation.Length == 0)
            return true;
        var delta = point - Vector(expectation);
        return Mathf.Abs(delta.x) <= tolerance && Mathf.Abs(delta.y) <= tolerance &&
            Mathf.Abs(delta.z) <= tolerance;
    }

    private static bool BoundsMatch(Vector3 min, Vector3 max, float[] expectedMin,
        float[] expectedMax, float tolerance) =>
        Finite(min) && Finite(max) && Near(min, expectedMin, tolerance) &&
        Near(max, expectedMax, tolerance);

    private static void VerifyGeometry(GameObject prefab, Model model, Observation row)
    {
        var filters = prefab.GetComponentsInChildren<MeshFilter>(true);
        row.meshCount = filters.Length;
        Check(row, filters.Length > 0, "Missing mesh filters");
        var min = Vector3.one * float.PositiveInfinity;
        var max = Vector3.one * float.NegativeInfinity;
        var usedMaterials = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var filter in filters)
        {
            var mesh = filter.sharedMesh;
            Check(row, mesh != null, "Missing shared mesh " + filter.name);
            if (mesh == null)
                continue;
            var vertices = mesh.vertices.Select(filter.transform.TransformPoint).ToArray();
            var valid = vertices.All(Finite);
            Check(row, valid && vertices.Length > 0, "Missing or non-finite vertices " + filter.name);
            if (valid)
                AddBounds(vertices, ref min, ref max);
            var uv = mesh.uv;
            row.vertexCount += vertices.Length;
            row.uvCount += uv.Length;
            Check(row, uv.Length == vertices.Length && uv.All(p => Finite(p.x) && Finite(p.y)),
                "Missing or invalid UV0 " + filter.name);
            var names = MaterialNames(filter.GetComponent<MeshRenderer>());
            Check(row, names.Length == mesh.subMeshCount, "Material slot count " + filter.name);
            for (var index = 0; index < mesh.subMeshCount; index++)
            {
                var indices = mesh.GetIndices(index);
                var validTriangles = mesh.GetTopology(index) == MeshTopology.Triangles &&
                    indices.Length > 0 && indices.Length % 3 == 0 &&
                    indices.All(i => i >= 0 && i < vertices.Length);
                Check(row, validTriangles, "Invalid triangle indices " + filter.name);
                if (!validTriangles)
                    continue;
                row.triangleCount += indices.Length / 3;
                if (index < names.Length)
                    usedMaterials.Add(names[index]);
                if (!valid)
                    continue;
                for (var i = 0; i < indices.Length; i += 3)
                    if (Vector3.Cross(vertices[indices[i + 1]] - vertices[indices[i]],
                        vertices[indices[i + 2]] - vertices[indices[i]]).sqrMagnitude <= 1e-16f)
                        row.degenerateTriangles++;
            }
        }
        if (Finite(min) && Finite(max))
        {
            row.observedMin = Values(min);
            row.observedMax = Values(max);
        }
        Check(row, BoundsMatch(min, max, model.boundsMin, model.boundsMax, model.boundsTolerance),
            "Aggregate world-space bounds outside rubric");
        Check(row, row.triangleCount > row.degenerateTriangles, "No nondegenerate triangles");
        row.materials = usedMaterials.ToArray();
        Check(row, !usedMaterials.Contains("<null>") && usedMaterials.Count > 0,
            "Missing material binding");
        if (model.materials != null && model.materials.Length > 0)
            Check(row, usedMaterials.SetEquals(model.materials), "Imported material inventory differs");

        foreach (var module in model.modules ?? Array.Empty<Module>())
        {
            var matches = filters.Where(filter => filter.name.EndsWith(
                ":module:" + module.id, StringComparison.Ordinal)).ToArray();
            var seen = new ModuleObservation { id = module.id, count = matches.Length,
                expectedMin = module.boundsMin, expectedMax = module.boundsMax,
                expectedMaterial = module.material };
            if (matches.Length == 1 && matches[0].sharedMesh != null)
            {
                var filter = matches[0];
                var low = Vector3.one * float.PositiveInfinity;
                var high = Vector3.one * float.NegativeInfinity;
                AddBounds(filter.sharedMesh.vertices.Select(filter.transform.TransformPoint), ref low, ref high);
                if (Finite(low) && Finite(high))
                {
                    seen.observedMin = Values(low);
                    seen.observedMax = Values(high);
                }
                seen.materials = MaterialNames(filter.GetComponent<MeshRenderer>());
                seen.passed = BoundsMatch(low, high, module.boundsMin, module.boundsMax, model.boundsTolerance) &&
                    (string.IsNullOrEmpty(module.material) || seen.materials.Contains(module.material));
            }
            row.modules.Add(seen);
            Check(row, seen.passed, "Named module bounds, count, or material differs " + module.id);
        }
    }

    private static void NegativeSocket(GameObject prefab, Model model, Observation row, Socket socket, bool reflected)
    {
        var negative = new Negative { id = reflected ? "socket_x_reflection" : "socket_missing",
            socketId = socket?.id, applicable = socket != null };
        row.negatives.Add(negative);
        if (socket == null)
            return;
        GameObject clone = null;
        try
        {
            clone = UnityEngine.Object.Instantiate(prefab);
            var baseline = SocketPosition(clone, socket, model.coordinateTolerance);
            Check(row, baseline.passed, "Mutation baseline socket invalid " + socket.id);
            if (!baseline.passed)
                return;
            var transform = Sockets(clone, socket.id).Single();
            if (reflected)
            {
                var point = transform.position;
                point.x = -point.x;
                transform.position = point;
            }
            else
                transform.name += "_removed";
            var mutated = SocketPosition(clone, socket, model.coordinateTolerance);
            negative.observed = mutated.observed;
            negative.detected = !mutated.passed;
            Check(row, negative.detected, "Injected mutation escaped " + negative.id);
        }
        finally
        {
            if (clone != null)
                UnityEngine.Object.DestroyImmediate(clone);
            negative.cleanedUp = clone == null;
            Check(row, negative.cleanedUp, "Mutation clone leaked");
        }
    }

    private static void Inspect(Model model, Observation row)
    {
        row.sha256 = Sha256(model.path);
        Check(row, row.sha256 == model.sha256, "FBX changed between staging and import");
        var options = ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate;
        AssetDatabase.ImportAsset(model.path, options);
        var importer = AssetImporter.GetAtPath(model.path) as ModelImporter;
        if (importer == null)
            throw new InvalidOperationException("Asset is not a Unity model");
        importer.preserveHierarchy = true;
        importer.SaveAndReimport();
        row.guid = AssetDatabase.AssetPathToGUID(model.path);
        row.metaSha256 = Sha256(model.path + ".meta");
        AssetDatabase.ImportAsset(model.path, options);
        row.guidAfterReimport = AssetDatabase.AssetPathToGUID(model.path);
        row.metaSha256AfterReimport = Sha256(model.path + ".meta");
        Check(row, row.guid.Length == 32 && row.guid == row.guidAfterReimport &&
            row.metaSha256 == row.metaSha256AfterReimport, "GUID or metadata changed on forced reimport");
        importer = (ModelImporter)AssetImporter.GetAtPath(model.path);
        row.preserveHierarchy = importer.preserveHierarchy;
        row.bakeAxisConversion = importer.bakeAxisConversion;
        row.useFileScale = importer.useFileScale;
        row.globalScale = importer.globalScale;
        row.fileScale = importer.fileScale;
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(model.path);
        if (prefab == null)
            throw new InvalidOperationException("Missing imported GameObject");
        VerifyGeometry(prefab, model, row);
        var sockets = model.sockets ?? Array.Empty<Socket>();
        foreach (var socket in sockets)
        {
            var seen = SocketPosition(prefab, socket, model.coordinateTolerance);
            row.sockets.Add(seen);
            Check(row, seen.passed, "Missing, duplicated, or displaced socket " + socket.id);
        }
        NegativeSocket(prefab, model, row, sockets.FirstOrDefault(), false);
        NegativeSocket(prefab, model, row,
            sockets.FirstOrDefault(socket => Mathf.Abs(socket.position[0]) > model.coordinateTolerance), true);
        Check(row, Sha256(model.path) == row.sha256, "Import mutated staged FBX");
    }

    private static string RequiredArg(string[] args, string name)
    {
        var index = Array.IndexOf(args, name);
        if (index < 0 || index + 1 >= args.Length)
            throw new ArgumentException("Missing " + name);
        return args[index + 1];
    }

    public static void Run()
    {
        var args = Environment.GetCommandLineArgs();
        var output = RequiredArg(args, "-phase13Result");
        var receipt = new Receipt { unityVersion = Application.unityVersion };
        try
        {
            if (receipt.unityVersion != "6000.6.3f1")
                throw new InvalidOperationException("Unexpected Unity editor version " + receipt.unityVersion);
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(RequiredArg(args, "-phase13Input")));
            foreach (var model in input.models)
            {
                var row = new Observation { attemptId = model.attemptId, kind = model.kind,
                    path = model.path, expectedMin = model.boundsMin, expectedMax = model.boundsMax,
                    expectedMaterials = model.materials };
                receipt.observations.Add(row);
                var stopwatch = System.Diagnostics.Stopwatch.StartNew();
                try { Inspect(model, row); }
                catch (Exception error) { row.failures.Add(error.ToString()); }
                finally { row.elapsedSeconds = stopwatch.Elapsed.TotalSeconds; }
                row.passed = row.failures.Count == 0;
                Debug.Log("Phase13 " + row.attemptId + "/" + row.kind + " " +
                    (row.passed ? "PASS" : string.Join(" | ", row.failures)));
            }
        }
        catch (Exception error)
        {
            receipt.fatal = error.ToString();
            throw;
        }
        finally { File.WriteAllText(output, JsonUtility.ToJson(receipt, true)); }
    }
}
