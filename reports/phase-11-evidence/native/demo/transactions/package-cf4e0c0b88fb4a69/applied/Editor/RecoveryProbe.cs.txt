using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace PolyForge.Editor
{
    [Serializable] public class RecoveryAssetIdentity
    {
        public string path;
        public string guid;
        public string[] object_ids;
        public string[] references;
        public int missing_components;
    }
    [Serializable] public class RecoveryIdentityReport
    {
        public string schema_version = "1.0.0";
        public string unity_version;
        public RecoveryAssetIdentity[] assets;
    }

    // Pinned Editor APIs: installed UnityEditor.xml AssetDatabase.TryGetGUIDAndLocalFileIdentifier
    // (Object, out string, out Int64), LoadAllAssetsAtPath and SerializedObject.GetIterator.
    public static class RecoveryProbe
    {
        static string Identity(UnityEngine.Object value)
        {
            if (value == null) return "NULL";
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out string guid, out long id))
                throw new InvalidOperationException("Cannot observe persistent identity: " + value.name);
            return guid + ":" + id;
        }

        public static RecoveryIdentityReport Observe()
        {
            if (Application.unityVersion != "6000.6.3f1") throw new Exception("Pinned Editor required");
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var rows = new List<RecoveryAssetIdentity>();
            var paths = AssetDatabase.GetAllAssetPaths()
                .Where(p => p.StartsWith("Assets/PolyForgeGenerated/", StringComparison.Ordinal)
                    && !AssetDatabase.IsValidFolder(p)).OrderBy(p => p, StringComparer.Ordinal).ToArray();
            if (paths.Length == 0 || paths.Length > 4096) throw new Exception("Invalid managed asset count");
            int properties = 0;
            foreach (string path in paths)
            {
                var objects = new HashSet<UnityEngine.Object>(AssetDatabase.LoadAllAssetsAtPath(path).Where(o => o != null));
                int missing = 0;
                foreach (var root in objects.OfType<GameObject>().ToArray())
                    foreach (var component in root.GetComponentsInChildren<Component>(true))
                        if (component == null) missing++; else objects.Add(component);
                var references = new List<string>();
                foreach (var value in objects)
                {
                    string owner = Identity(value);
                    using (var serialized = new SerializedObject(value))
                    {
                        var property = serialized.GetIterator();
                        while (property.Next(true))
                        {
                            if (++properties > 1000000) throw new Exception("Managed property budget exceeded");
                            if (property.propertyType == SerializedPropertyType.ObjectReference)
                                references.Add(owner + "/" + property.propertyPath + "=" + Identity(property.objectReferenceValue));
                        }
                    }
                }
                rows.Add(new RecoveryAssetIdentity {
                    path = path, guid = AssetDatabase.AssetPathToGUID(path), missing_components = missing,
                    object_ids = objects.Select(Identity).Distinct().OrderBy(s => s, StringComparer.Ordinal).ToArray(),
                    references = references.OrderBy(s => s, StringComparer.Ordinal).ToArray()
                });
            }
            return new RecoveryIdentityReport {unity_version = Application.unityVersion, assets = rows.ToArray()};
        }

        public static void ObserveBatch()
        {
            try
            {
                string[] args = Environment.GetCommandLineArgs();
                int index = Array.IndexOf(args, "-polyforgeOutput");
                if (index < 0 || index + 1 >= args.Length) throw new Exception("Missing managed output path");
                File.WriteAllText(args[index + 1], JsonUtility.ToJson(Observe(), true));
                EditorApplication.Exit(0);
            }
            catch (Exception error) {Debug.LogException(error); EditorApplication.Exit(5);}
        }
    }
}
