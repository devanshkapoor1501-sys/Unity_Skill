using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

public static class ModelingImportProbe
{
    private const float Tolerance = 0.005f;
    [Serializable] private class Input { public Model[] models; }
    [Serializable] private class Model
    {
        public string path;
        public float[] lo, hi;
        public int meshCount;
        public Socket[] sockets;
        public Module[] modules;
        public string[] materialIds;
        public MaterialTriangles[] materialTriangles;
    }
    [Serializable] private class MaterialTriangles { public string id; public int triangles; }
    [Serializable] private class Socket { public string id; public float[] position; }
    [Serializable] private class Module { public string id; public float[] lo, hi; public string[] materialIds; }
    [Serializable] private class Receipt
    {
        public int models;
        public bool passed;
        public string error;
        public string unityVersion;
        public List<ModelObservation> observations = new List<ModelObservation>();
    }
    [Serializable] private class ModelObservation
    {
        public string path, guidBeforeReimport, guidAfterReimport;
        public string metaSha256Before, metaSha256After;
        public bool preserveHierarchy, bakeAxisConversion, useFileScale, passed;
        public float globalScale, fileScale;
        public int meshCount;
        public float[] lo, hi;
        public string[] expectedMaterialIds, materialNames, materialSlotNames;
        public int materialSlotCount;
        public MaterialTriangles[] expectedMaterialTriangles, materialTriangles;
        public List<TransformObservation> transforms = new List<TransformObservation>();
        public List<SocketObservation> sockets = new List<SocketObservation>();
        public List<ModuleObservation> modules = new List<ModuleObservation>();
        public List<MutationObservation> mutants = new List<MutationObservation>();
        public List<ParentObservation> parentCases = new List<ParentObservation>();
    }
    [Serializable] private class TransformObservation
    {
        public string path;
        public float[] localMatrix, worldMatrix;
        public float localDeterminant, worldDeterminant;
    }
    [Serializable] private class SocketObservation
    {
        public string id;
        public float[] expected, observed;
        public int matchCount;
    }
    [Serializable] private class ModuleObservation
    {
        public string id;
        public int matchCount, materialCount;
        public float[] expectedLo, expectedHi, lo, hi;
        public string[] expectedMaterialIds, materialNames;
    }
    [Serializable] private class MutationObservation
    {
        public string id, reason;
        public bool applicable, detected, cleanedUp;
        public List<TransformObservation> transforms = new List<TransformObservation>();
    }
    [Serializable] private class ParentObservation
    {
        public string id;
        public int socketCount, vertexCount;
        public float maxSocketError, maxVertexError;
        public bool restored, cleanedUp;
        public float[] parentWorldMatrix;
        public List<TransformObservation> transforms = new List<TransformObservation>();
    }
    // Only this precise failure type counts as coordinate mutant detection.
    private sealed class CoordinateMismatch : Exception
    {
        public CoordinateMismatch(string message) : base(message) { }
    }
    private static Vector3 Vector(float[] value) => new Vector3(value[0], value[1], value[2]);
    private static float[] Values(Vector3 value) => new[] { value.x, value.y, value.z };
    private static float[] Matrix(Matrix4x4 value)
    {
        var result = new float[16];
        for (var row = 0; row < 4; row++)
            for (var column = 0; column < 4; column++) result[row * 4 + column] = value[row, column];
        return result;
    }
    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidDataException(message);
    }
    private static string MetaSha256(string assetPath)
    {
        using (var sha256 = SHA256.Create())
            return BitConverter.ToString(sha256.ComputeHash(File.ReadAllBytes(assetPath + ".meta")))
                .Replace("-", "").ToLowerInvariant();
    }
    private static string TransformPath(Transform value) => value.parent == null
        ? value.name : TransformPath(value.parent) + "/" + value.name;
    private static List<TransformObservation> Trace(GameObject root) => root.GetComponentsInChildren<Transform>(true)
        .Select(t => new TransformObservation
        {
            path = TransformPath(t),
            localMatrix = Matrix(Matrix4x4.TRS(t.localPosition, t.localRotation, t.localScale)),
            worldMatrix = Matrix(t.localToWorldMatrix),
            localDeterminant = Matrix4x4.TRS(t.localPosition, t.localRotation, t.localScale).determinant,
            worldDeterminant = t.localToWorldMatrix.determinant
        }).ToList();
    private static Transform[] SocketMatches(GameObject root, string id) => root.GetComponentsInChildren<Transform>(true)
        .Where(t => t.name.EndsWith(":socket:" + id, StringComparison.Ordinal)).ToArray();
    private static MeshFilter[] ModuleMatches(GameObject root, string id) => root.GetComponentsInChildren<MeshFilter>(true)
        .Where(t => t.name.EndsWith(":module:" + id + "_evaluated", StringComparison.Ordinal)).ToArray();
    private static void Bounds(MeshFilter[] filters, out Vector3 min, out Vector3 max)
    {
        min = Vector3.one * float.PositiveInfinity;
        max = Vector3.one * float.NegativeInfinity;
        foreach (var filter in filters)
        {
            var mesh = filter.sharedMesh;
            Check(mesh != null && mesh.vertexCount > 0 && mesh.uv.Length == mesh.vertexCount,
                  "Missing geometry or UVs for " + filter.name);
            foreach (var vertex in mesh.vertices)
            {
                var point = filter.transform.TransformPoint(vertex);
                min = Vector3.Min(min, point);
                max = Vector3.Max(max, point);
            }
        }
    }
    private static void CheckBounds(Vector3 lo, Vector3 hi, float[] expectedLo, float[] expectedHi, string label)
    {
        if (!(Vector3.Distance(lo, Vector(expectedLo)) < Tolerance && Vector3.Distance(hi, Vector(expectedHi)) < Tolerance))
            throw new CoordinateMismatch($"Bounds for {label}: observed {lo} to {hi}, expected {Vector(expectedLo)} to {Vector(expectedHi)}");
    }
    private static void Coordinates(GameObject root, Model model, ModelObservation observation = null)
    {
        var filters = root.GetComponentsInChildren<MeshFilter>(true);
        Check(filters.Length == model.meshCount, "Wrong mesh inventory for " + model.path);
        Bounds(filters, out var lo, out var hi);
        if (observation != null)
        {
            observation.meshCount = filters.Length;
            observation.lo = Values(lo);
            observation.hi = Values(hi);
            observation.transforms = Trace(root);
        }
        // Collect all observations before asserting so a failed baseline retains sign evidence.
        var socketRows = (model.sockets ?? new Socket[0]).Select(socket =>
        {
            var matches = SocketMatches(root, socket.id);
            return new SocketObservation { id = socket.id, expected = socket.position,
                observed = matches.Length == 1 ? Values(matches[0].position) : null, matchCount = matches.Length };
        }).ToList();
        if (observation != null) observation.sockets = socketRows;
        var moduleRows = (model.modules ?? new Module[0]).Select(module =>
        {
            var matches = ModuleMatches(root, module.id);
            var row = new ModuleObservation { id = module.id, matchCount = matches.Length,
                expectedLo = module.lo, expectedHi = module.hi, expectedMaterialIds = module.materialIds };
            if (matches.Length == 1)
            {
                Bounds(matches, out var moduleLo, out var moduleHi);
                row.lo = Values(moduleLo);
                row.hi = Values(moduleHi);
                var renderer = matches[0].GetComponent<MeshRenderer>();
                Check(renderer != null, "Missing renderer for module " + module.id);
                row.materialNames = renderer.sharedMaterials.Select(m => m == null ? "<null>" : m.name).ToArray();
                row.materialCount = row.materialNames.Length;
            }
            return row;
        }).ToList();
        if (observation != null) observation.modules = moduleRows;
        var renderers = root.GetComponentsInChildren<Renderer>(true);
        var materialSlots = renderers.SelectMany(renderer => renderer.sharedMaterials).ToArray();
        var materialSlotNames = materialSlots.Select(material => material == null ? "<null>" : material.name)
            .OrderBy(name => name, StringComparer.Ordinal).ToArray();
        var materialNames = materialSlotNames.Distinct(StringComparer.Ordinal).ToArray();
        if (observation != null)
        {
            observation.expectedMaterialIds = model.materialIds;
            observation.materialNames = materialNames;
            observation.materialSlotNames = materialSlotNames;
            observation.materialSlotCount = materialSlots.Length;
        }
        Check(renderers.All(renderer => renderer.sharedMaterials.Length > 0) && materialSlots.All(material => material != null),
            "Missing material slots for " + model.path);
        if (model.materialIds != null)
        {
            var expectedMaterials = model.materialIds.OrderBy(name => name, StringComparer.Ordinal).ToArray();
            Check(materialNames.SequenceEqual(expectedMaterials.Distinct(StringComparer.Ordinal)),
                $"Aggregate material inventory differs for {model.path}: observed [{string.Join(",", materialNames)}], expected [{string.Join(",", expectedMaterials)}]");
            if (model.meshCount == 1 && (model.modules == null || model.modules.Length == 0))
                Check(materialSlotNames.SequenceEqual(expectedMaterials),
                    $"LOD material slots differ for {model.path}: observed [{string.Join(",", materialSlotNames)}], expected [{string.Join(",", expectedMaterials)}]");
        }
        var triangleCounts = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var filter in filters)
        {
            var mesh = filter.sharedMesh;
            var renderer = filter.GetComponent<MeshRenderer>();
            Check(renderer != null, "Missing mesh renderer for " + filter.name);
            var slots = renderer.sharedMaterials;
            Check(slots.Length == mesh.subMeshCount, "Material/submesh inventory differs for " + filter.name);
            for (var submesh = 0; submesh < mesh.subMeshCount; submesh++)
            {
                Check(slots[submesh] != null, "Unbound material submesh for " + filter.name);
                Check(mesh.GetTopology(submesh) == MeshTopology.Triangles, "Non-triangle submesh for " + filter.name);
                var indices = mesh.GetTriangles(submesh);
                Check(indices.Length > 0 && indices.Length % 3 == 0, "Empty or invalid material submesh for " + filter.name);
                var id = slots[submesh].name;
                triangleCounts.TryGetValue(id, out var previous);
                triangleCounts[id] = checked(previous + indices.Length / 3);
            }
        }
        var observedTriangles = triangleCounts.OrderBy(pair => pair.Key, StringComparer.Ordinal)
            .Select(pair => new MaterialTriangles { id = pair.Key, triangles = pair.Value }).ToArray();
        if (observation != null)
        {
            observation.expectedMaterialTriangles = model.materialTriangles;
            observation.materialTriangles = observedTriangles;
        }
        if (model.materialTriangles != null)
        {
            Check(model.materialTriangles.All(row => !string.IsNullOrEmpty(row.id) && row.triangles > 0) &&
                model.materialTriangles.Select(row => row.id).Distinct(StringComparer.Ordinal).Count() == model.materialTriangles.Length,
                "Invalid expected material triangle histogram for " + model.path);
            var expectedTriangles = model.materialTriangles.OrderBy(row => row.id, StringComparer.Ordinal).ToArray();
            Check(observedTriangles.Length == expectedTriangles.Length && observedTriangles.Zip(expectedTriangles,
                (actual, expected) => actual.id == expected.id && actual.triangles == expected.triangles).All(equal => equal),
                $"Material triangle histogram differs for {model.path}: observed [{string.Join(",", observedTriangles.Select(row => row.id + "=" + row.triangles))}], expected [{string.Join(",", expectedTriangles.Select(row => row.id + "=" + row.triangles))}]");
        }
        CheckBounds(lo, hi, model.lo, model.hi, model.path);
        foreach (var row in socketRows)
        {
            Check(row.matchCount == 1, $"Socket inventory differs for {model.path}: {row.id}");
            if (!(Vector3.Distance(Vector(row.observed), Vector(row.expected)) < Tolerance))
                throw new CoordinateMismatch($"Socket {row.id} moved in {model.path}: observed {Vector(row.observed)}, expected {Vector(row.expected)}");
        }
        foreach (var row in moduleRows)
        {
            Check(row.matchCount == 1, $"Module inventory differs for {model.path}: {row.id}");
            CheckBounds(Vector(row.lo), Vector(row.hi), row.expectedLo, row.expectedHi, model.path + ":module:" + row.id);
            Check(row.materialNames.OrderBy(n => n, StringComparer.Ordinal).SequenceEqual(
                (row.expectedMaterialIds ?? new string[0]).OrderBy(n => n, StringComparer.Ordinal)),
                $"Material inventory differs for {model.path}:{row.id}: observed [{string.Join(",", row.materialNames)}], expected [{string.Join(",", row.expectedMaterialIds ?? new string[0])}]");
        }
    }
    private static void Mutant(GameObject prefab, Model model, ModelObservation observation, string id, bool applicable, Action<GameObject> mutate)
    {
        var row = new MutationObservation { id = id, applicable = applicable };
        observation.mutants.Add(row);
        if (!applicable) { row.reason = "No asymmetric expected X coordinate"; row.cleanedUp = true; return; }
        GameObject instance = null;
        try
        {
            instance = UnityEngine.Object.Instantiate(prefab);
            mutate(instance);
            row.transforms = Trace(instance);
            try { Coordinates(instance, model); }
            catch (CoordinateMismatch failure) { row.detected = true; row.reason = failure.Message; }
            Check(row.detected, "Coordinate validator accepted mutant " + id + " for " + model.path);
        }
        finally
        {
            if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
            row.cleanedUp = instance == null;
            Check(row.cleanedUp, "Mutant instance leaked: " + id);
        }
    }
    private static void ParentCase(GameObject prefab, Model model, ModelObservation observation, bool mirrored)
    {
        var row = new ParentObservation { id = mirrored ? "nested_mirrored" : "nested_nonuniform" };
        observation.parentCases.Add(row);
        GameObject outer = null, inner = null, instance = null;
        try
        {
            outer = new GameObject("probe_outer");
            outer.transform.SetPositionAndRotation(new Vector3(4.25f, -1.3f, 2.7f), Quaternion.Euler(17, 39, -23));
            outer.transform.localScale = new Vector3(mirrored ? -1.7f : 1.7f, 0.65f, 1.25f);
            inner = new GameObject("probe_inner");
            inner.transform.SetParent(outer.transform, false);
            inner.transform.localPosition = new Vector3(-0.8f, 1.6f, 0.45f);
            inner.transform.localRotation = Quaternion.Euler(-31, 12, 48);
            inner.transform.localScale = new Vector3(0.8f, 1.4f, 0.9f);
            instance = UnityEngine.Object.Instantiate(prefab);
            instance.transform.SetParent(inner.transform, false);
            var matrix = inner.transform.localToWorldMatrix;
            row.parentWorldMatrix = Matrix(matrix);
            row.transforms = Trace(instance);
            foreach (var socket in model.sockets ?? new Socket[0])
            {
                var original = SocketMatches(prefab, socket.id);
                var actual = SocketMatches(instance, socket.id);
                Check(original.Length == 1 && actual.Length == 1, "Parent-case socket inventory: " + socket.id);
                var expected = matrix.MultiplyPoint3x4(original[0].position);
                row.maxSocketError = Mathf.Max(row.maxSocketError, Vector3.Distance(expected, actual[0].position));
                row.socketCount++;
            }
            var source = prefab.GetComponentsInChildren<MeshFilter>(true);
            var target = instance.GetComponentsInChildren<MeshFilter>(true);
            Check(source.Length == target.Length, "Parent-case mesh inventory changed");
            for (var i = 0; i < source.Length; i++)
            {
                Check(source[i].sharedMesh == target[i].sharedMesh, "Parent-case mesh order changed");
                foreach (var vertex in source[i].sharedMesh.vertices)
                {
                    var original = source[i].transform.localToWorldMatrix.MultiplyPoint3x4(vertex);
                    var expected = matrix.MultiplyPoint3x4(original);
                    var actual = target[i].transform.TransformPoint(vertex);
                    row.maxVertexError = Mathf.Max(row.maxVertexError, Vector3.Distance(expected, actual));
                    row.vertexCount++;
                }
            }
            Check(row.maxSocketError < Tolerance && row.maxVertexError < Tolerance, "Nested parent transform mismatch: " + row.id);
            instance.transform.SetParent(null, false);
            Coordinates(instance, model);
            row.restored = true;
        }
        finally
        {
            if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
            if (outer != null) UnityEngine.Object.DestroyImmediate(outer);
            if (inner != null) UnityEngine.Object.DestroyImmediate(inner);
            row.cleanedUp = instance == null && outer == null && inner == null;
            Check(row.cleanedUp, "Parent-case objects leaked: " + row.id);
        }
    }
    public static void Run()
    {
        var args = Environment.GetCommandLineArgs();
        var resultPath = args[Array.IndexOf(args, "-modelingResult") + 1];
        var receipt = new Receipt { unityVersion = Application.unityVersion };
        try
        {
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(args[Array.IndexOf(args, "-modelingInput") + 1]));
            receipt.models = input.models.Length;
            Check(Application.unityVersion == "6000.6.3f1", "Wrong Editor version");
            foreach (var model in input.models)
            {
                var observation = new ModelObservation { path = model.path };
                receipt.observations.Add(observation);
                var options = ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate;
                AssetDatabase.ImportAsset(model.path, options);
                var importer = (ModelImporter)AssetImporter.GetAtPath(model.path);
                importer.preserveHierarchy = true;
                importer.SaveAndReimport();
                observation.guidBeforeReimport = AssetDatabase.AssetPathToGUID(model.path);
                Check(observation.guidBeforeReimport.Length == 32, "Missing import GUID for " + model.path);
                observation.metaSha256Before = MetaSha256(model.path);
                AssetDatabase.ImportAsset(model.path, options);
                observation.guidAfterReimport = AssetDatabase.AssetPathToGUID(model.path);
                observation.metaSha256After = MetaSha256(model.path);
                Check(observation.metaSha256Before == observation.metaSha256After, "Unstable meta bytes for " + model.path);
                importer = (ModelImporter)AssetImporter.GetAtPath(model.path);
                observation.preserveHierarchy = importer.preserveHierarchy;
                observation.bakeAxisConversion = importer.bakeAxisConversion;
                observation.useFileScale = importer.useFileScale;
                observation.globalScale = importer.globalScale;
                observation.fileScale = importer.fileScale;
                Check(observation.guidAfterReimport == observation.guidBeforeReimport, "Unstable GUID for " + model.path);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(model.path);
                Check(prefab != null, "Missing imported model " + model.path);
                Coordinates(prefab, model, observation);
                var outlet = (model.sockets ?? new Socket[0]).FirstOrDefault(s => s.id == "outlet" && Mathf.Abs(s.position[0]) * 2 >= Tolerance);
                Mutant(prefab, model, observation, "outlet_x_reflection", outlet != null, instance =>
                {
                    var socket = SocketMatches(instance, "outlet").Single();
                    var reflected = socket.position;
                    reflected.x = -reflected.x;
                    socket.localPosition = socket.parent == null ? reflected : socket.parent.worldToLocalMatrix.MultiplyPoint3x4(reflected);
                });
                var asymmetric = Mathf.Abs(model.lo[0] + model.hi[0]) >= Tolerance ||
                    (model.sockets ?? new Socket[0]).Any(s => Mathf.Abs(s.position[0]) * 2 >= Tolerance) ||
                    (model.modules ?? new Module[0]).Any(m => Mathf.Abs(m.lo[0] + m.hi[0]) >= Tolerance);
                Mutant(prefab, model, observation, "whole_root_x_reflection", asymmetric, instance =>
                {
                    // F * R * S = (F * R * F) * (F * S), including rotated roots.
                    var rotation = instance.transform.rotation;
                    instance.transform.rotation = new Quaternion(rotation.x, -rotation.y, -rotation.z, rotation.w);
                    var scale = instance.transform.localScale;
                    scale.x = -scale.x;
                    instance.transform.localScale = scale;
                    var position = instance.transform.position;
                    position.x = -position.x;
                    instance.transform.position = position;
                });
                ParentCase(prefab, model, observation, false);
                ParentCase(prefab, model, observation, true);
                observation.passed = true;
                Debug.Log("PolyForge modeling import passed " + model.path + " " + observation.guidAfterReimport);
            }
            receipt.passed = true;
        }
        catch (Exception failure)
        {
            receipt.error = failure.ToString();
            throw;
        }
        finally { File.WriteAllText(resultPath, JsonUtility.ToJson(receipt, true)); }
    }
}
