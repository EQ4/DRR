#!/usr/bin/php
<?php

include_once(__DIR__ . '/../common.php');

function get_column_list($table_name) {
  global $db;
  $res = $db->query("pragma table_info( $table_name )");

  return array_map(function($row) { 
    return $row['name'];
  }, sql_all($res));
}

foreach($schema as $table_name => $tbl_schema) {
  $existing_column_name_list = get_column_list($table_name);

  // This means we need to create the table
  if (count($existing_column_name_list) == 0) {

    $schema = implode (',', sql_kv($tbl_schema, '', ''));
    $db->exec("create table $table_name ( $schema )");

  } else {

    // Otherwise we may need to add columns to the table
    $our_column_name_list = array_keys($tbl_schema);

    $column_to_add_list = array_diff($our_column_name_list, $existing_column_name_list);

    if(count($column_to_add_list)) {
      echo "Adding the following columns from $tbl_name:";
      print_r($column_to_add_list);

      foreach($column_to_add_list as $column_to_add) {
        $column_to_add_schema = $tbl_schema[$column_to_add];
        $db->exec("alter table $table_name add column $column_to_add $column_to_add_schema");
      }

      // If we added columns then we need to revisit our pragma
      $existing_column_name_list = get_column_list($table_name);
    }
    $column_to_remove_list = array_diff($existing_column_name_list, $our_column_name_list);

    // See if we need to remove any columns
    if (count($column_to_remove_list) > 0) {
      echo "Removing the following columns from $tbl_name:";
      print_r($column_to_remove_list);

      $our_schema = implode(',', sql_kv($tbl_schema, '', ''));
      $our_columns = implode(',', $our_column_name_list);

      $drop_column_sql = "
        CREATE TEMPORARY TABLE my_backup($our_schema);
        INSERT INTO my_backup SELECT $our_columns FROM $table_name;
        DROP TABLE $table_name;
        CREATE TABLE $table_name($our_schema);
        INSERT INTO $table_name SELECT $our_columns FROM my_backup;
        DROP TABLE my_backup;
      ";

      foreach(explode('\n', trim($drop_column_sql)) as $sql_line) {
        $db->exec($sql_line);
      }
    }
  }
}
