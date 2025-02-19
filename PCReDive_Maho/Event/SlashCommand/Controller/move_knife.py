﻿from discord_slash.utils.manage_commands import create_option, create_choice
import Discord_client
import Module.DB_control
import Module.Authentication
import Module.check_week
import Module.check_boss
import Module.Update

# !移動 [週目] [幾王] [第幾刀] 到 [週目] [幾王]
@Discord_client.slash.subcommand( base="controller", 
                                  name="move_knife", 
                                  description="調動某刀",
                                  options=[
                                    create_option(
                                      name="週目",
                                      description="目標週目",
                                      option_type=4,
                                      required=True
                                    ),
                                    create_option(
                                      name="boss",
                                      description="目標boss",
                                      option_type=4,
                                      required=True,
                                      choices=[
                                        create_choice(name="1王", value=1),
                                        create_choice(name="2王", value=2),
                                        create_choice(name="3王", value=3),
                                        create_choice(name="4王", value=4),
                                        create_choice(name="5王", value=5),
                                      ]
                                    ),
                                    create_option(
                                      name="刀表序號",
                                      description="該週目boss刀表上的第幾刀",
                                      option_type=4,
                                      required=True
                                    ),
                                    create_option(
                                      name="新週目",
                                      description="目的地週目",
                                      option_type=4,
                                      required=True
                                    ),
                                    create_option(
                                      name="新boss",
                                      description="目的地boss",
                                      option_type=4,
                                      required=True,
                                      choices=[
                                        create_choice(name="1王", value=1),
                                        create_choice(name="2王", value=2),
                                        create_choice(name="3王", value=3),
                                        create_choice(name="4王", value=4),
                                        create_choice(name="5王", value=5),
                                      ]
                                    )
                                  ],
                                  connector={"週目": "source_week", "boss": "source_boss", "刀表序號": "source_knife", "新週目": "destination_week", "新boss": "destination_boss"}
                                )
async def move_knife(ctx, source_week, source_boss, source_knife, destination_week, destination_boss):
  connection = await Module.DB_control.OpenConnection(ctx)
  if connection:
    ( now_week, now_boss, week_offset, group_serial ) = await Module.Authentication.IsController(ctx, '/controller move_knife', connection, ctx.guild.id) # check身分，並找出所屬組別
    if not group_serial == 0: # 如果是控刀手
      if Module.check_week.Check_week((now_week, now_boss, week_offset), source_week) and Module.check_week.Check_week((now_week, now_boss, week_offset), destination_week):
        if Module.check_boss.Check_boss((now_week, now_boss, week_offset), source_week, source_boss) and Module.check_boss.Check_boss((now_week, now_boss, week_offset), destination_week, destination_boss):
          # 尋找要刪除刀的序號
          delete_index = 0
          cursor = connection.cursor(prepared=True)
          sql = "SELECT serial_number,server_id, group_serial, boss, member_id, comment from princess_connect.knifes where server_id=? and group_serial=? and week=? and boss=? order by serial_number limit ?,1"
          data = (ctx.guild.id, group_serial, source_week, source_boss, source_knife-1)
          cursor.execute(sql, data)
          row = cursor.fetchone()
          cursor.close()
          if row:
            # 寫入刀表
            cursor = connection.cursor(prepared=True)
            sql = "INSERT INTO princess_connect.knifes (server_id, group_serial, member_id, week, boss, comment) VALUES (?, ?, ?, ?, ?, ?)"
            data = (row[1], row[2], row[4], destination_week ,destination_boss, row[5])
            cursor.execute(sql, data)
            cursor.close()

            # 刪除刀表
            cursor = connection.cursor(prepared=True)
            sql = "DELETE from princess_connect.knifes where serial_number=?"
            data = (row[0],)
            cursor.execute(sql, data)
            cursor.close()
            connection.commit()
            await ctx.send('第' + str(source_week) + '週目' + str(source_boss) + '王，移動完成!')
            await Module.Update.Update(ctx, ctx.guild.id, group_serial) # 更新刀表
          else:
            await ctx.send('該刀不存在喔!')
        else:
          await ctx.send('該王不存在喔!')
      else:
        await ctx.send('該週目不存在喔!')

    await Module.DB_control.CloseConnection(connection, ctx)