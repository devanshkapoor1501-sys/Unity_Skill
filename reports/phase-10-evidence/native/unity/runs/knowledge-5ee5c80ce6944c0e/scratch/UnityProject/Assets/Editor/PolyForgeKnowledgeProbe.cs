// Fixed trusted-local probe in a new empty project, never an original user project.
using System;
using System.IO;
using UnityEditor;
using UnityEngine;

public sealed class PolyForgeKnowledgeRecord : ScriptableObject { }
public static class PolyForgeKnowledgeProbe
{
    [Serializable] sealed class Checks
    {
        public bool known_record_found;
        public bool unrelated_type_excluded;
        public bool editor_assembly;
    }
    [Serializable] sealed class Observation
    {
        public string schema_version = "1.0.0";
        public string probe_id = "unity.typecache.v1";
        public string tool_version = Application.unityVersion;
        public Checks checks = new Checks();
        public string[] artifacts = new string[0];
    }
    public static void Run()
    {
        try
        {
            var observation = new Observation();
            bool found = false, unrelated = false;
            foreach (Type type in TypeCache.GetTypesDerivedFrom<ScriptableObject>())
            {
                found |= type == typeof(PolyForgeKnowledgeRecord);
                unrelated |= type == typeof(Transform);
            }
            observation.checks.known_record_found = found;
            observation.checks.unrelated_type_excluded = !unrelated;
            observation.checks.editor_assembly = typeof(TypeCache).Assembly.GetName().Name.StartsWith("UnityEditor");
            string[] args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "-polyforgeProbeOutput");
            if (index < 0 || index + 1 >= args.Length) throw new ArgumentException("Missing fixed probe output");
            File.WriteAllText(args[index + 1], JsonUtility.ToJson(observation, true) + "\n");
            EditorApplication.Exit(0);
        }
        catch (Exception error) { Debug.LogException(error); EditorApplication.Exit(6); }
    }
}
