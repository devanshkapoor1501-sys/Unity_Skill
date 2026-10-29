// Controlled qualification fixture. Copied only into the disposable managed test project.
// No NUnit attribute: running the user's ordinary test suite must never inject a fault.
using UnityEditor;
using UnityEngine;
using PolyForge;
using PolyForge.Editor;

public static class PolyForgeRecoveryFaultFixture
{
    public static void Inject()
    {
        var importer = AssetImporter.GetAtPath("Assets/PolyForgeGenerated/Models/robot_a.fbx") as ModelImporter;
        if (importer == null) throw new System.Exception("Expected managed fixture model");
        importer.globalScale = .25f;
        importer.SaveAndReimport();
        var path = PolyForgeBuilder.PrefabPath("robot_a");
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            root.transform.localScale = Vector3.one * 100;
            root.GetComponent<PrefabBinding>().sourceModel = null;
            PrefabUtility.SaveAsPrefabAsset(root, path);
        }
        finally {PrefabUtility.UnloadPrefabContents(root);}
        path = PolyForgeBuilder.PrefabPath("crate_a");
        root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            root.GetComponentInChildren<MeshRenderer>().sharedMaterial = null;
            PrefabUtility.SaveAsPrefabAsset(root, path);
        }
        finally {PrefabUtility.UnloadPrefabContents(root);}
        AssetDatabase.SaveAssets();
        EditorApplication.Exit(0);
    }
}
