// Independent acceptance fixture, copied only into a disposable test project.
using UnityEditor;
using UnityEngine;
using PolyForge;
using PolyForge.Editor;
public static class PolyForgeFaultProbe
{
    public static void DamageScale()
    {
        var path = PolyForgeBuilder.PrefabPath("robot_a");
        var root = PrefabUtility.LoadPrefabContents(path);
        root.transform.localScale = Vector3.one * 100;
        PrefabUtility.SaveAsPrefabAsset(root, path);
        PrefabUtility.UnloadPrefabContents(root);
        AssetDatabase.SaveAssets();
        EditorApplication.Exit(0);
    }
    public static void DamageScaleAndMaterial()
    {
        var robot = PolyForgeBuilder.PrefabPath("robot_a");
        var root = PrefabUtility.LoadPrefabContents(robot);
        root.transform.localScale = Vector3.one * 100;
        PrefabUtility.SaveAsPrefabAsset(root, robot);
        PrefabUtility.UnloadPrefabContents(root);
        var crate = PolyForgeBuilder.PrefabPath("crate_a");
        root = PrefabUtility.LoadPrefabContents(crate);
        root.GetComponentInChildren<MeshRenderer>().sharedMaterial = null;
        PrefabUtility.SaveAsPrefabAsset(root, crate);
        PrefabUtility.UnloadPrefabContents(root);
        AssetDatabase.SaveAssets();
        EditorApplication.Exit(0);
    }
}
